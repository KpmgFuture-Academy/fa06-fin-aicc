"""VITO STT 서비스 - AICC 파이프라인용

VITO(Return Zero) API를 사용한 한국어 음성 인식 서비스.
토큰 자동 갱신 및 싱글톤 패턴 적용.

토큰 갱신 정책:
- 토큰 유효기간: 6시간
- 만료 5분 전 자동 갱신
- 인증 실패 시 최대 3회 재시도
- API 요청 실패 시 토큰 만료 여부 확인 후 자동 재인증
"""

from __future__ import annotations

import io
import json
import logging
import struct
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# VITO API 엔드포인트
VITO_AUTH_URL = "https://openapi.vito.ai/v1/authenticate"
VITO_TRANSCRIBE_URL = "https://openapi.vito.ai/v1/transcribe"

# 토큰 관련 상수
TOKEN_VALIDITY_HOURS = 6  # 토큰 유효기간 (시간)
TOKEN_REFRESH_MARGIN_SECONDS = 300  # 만료 전 갱신 여유 시간 (5분)
AUTH_MAX_RETRIES = 3  # 인증 최대 재시도 횟수
AUTH_RETRY_DELAY_SECONDS = 2  # 재시도 간 대기 시간


class STTError(RuntimeError):
    """STT 처리 중 발생하는 예외"""
    pass


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """
    Raw INT16 PCM 데이터를 WAV 형식으로 변환

    Args:
        pcm_data: INT16 PCM 오디오 데이터
        sample_rate: 샘플레이트 (기본 16000Hz)
        channels: 채널 수 (기본 1 = 모노)
        sample_width: 샘플 크기 바이트 (기본 2 = 16bit)

    Returns:
        WAV 형식의 바이트 데이터
    """
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    wav_buffer.seek(0)
    return wav_buffer.read()


@dataclass
class STTSegment:
    """음성 인식 세그먼트"""
    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    confidence: Optional[float] = None
    speaker: Optional[str] = None


@dataclass
class STTResult:
    """음성 인식 결과"""
    text: str
    language: Optional[str] = None
    segments: list[STTSegment] = field(default_factory=list)
    raw: Optional[dict[str, Any]] = None


class AICCSTTService:
    """AICC용 VITO STT 서비스 (싱글톤)

    특징:
    - 토큰 자동 갱신 (6시간 유효, 5분 전 갱신)
    - 인증 실패 시 자동 재시도 (최대 3회)
    - 스레드 안전 (Lock 사용)
    - API 요청 실패 시 토큰 재발급 후 재시도
    - 화자 분리(diarization) 지원
    - 한국어 최적화

    사용 예:
        stt = AICCSTTService.get_instance()
        result = stt.transcribe(audio_bytes)
        print(result.text)
    """

    _instance: Optional["AICCSTTService"] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        """직접 생성하지 말고 get_instance() 사용"""
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._token_lock = threading.Lock()  # 토큰 갱신 시 스레드 안전성 보장
        self._session = requests.Session()
        self._timeout = settings.vito_stt_timeout

        # 초기 인증
        self._ensure_valid_token()

    @classmethod
    def get_instance(cls) -> "AICCSTTService":
        """싱글톤 인스턴스 반환 (스레드 안전)"""
        if cls._instance is None:
            with cls._instance_lock:
                # Double-checked locking
                if cls._instance is None:
                    if not settings.vito_client_id or not settings.vito_client_secret:
                        raise STTError(
                            "VITO STT 설정이 없습니다. "
                            ".env 파일에 VITO_CLIENT_ID와 VITO_CLIENT_SECRET을 설정하세요."
                        )
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 리셋 (테스트용)"""
        with cls._instance_lock:
            cls._instance = None

    def _ensure_valid_token(self) -> None:
        """토큰 유효성 확인 및 필요시 갱신 (스레드 안전)"""
        current_time = time.time()

        # 토큰이 없거나 만료 임박 시 갱신
        if self._token is None or current_time > self._token_expiry - TOKEN_REFRESH_MARGIN_SECONDS:
            with self._token_lock:
                # Double-checked locking: Lock 획득 후 다시 확인
                if self._token is None or current_time > self._token_expiry - TOKEN_REFRESH_MARGIN_SECONDS:
                    self._authenticate_with_retry()

    def _authenticate_with_retry(self) -> None:
        """VITO API 인증 토큰 발급 (재시도 로직 포함)"""
        last_error: Optional[Exception] = None

        for attempt in range(1, AUTH_MAX_RETRIES + 1):
            try:
                self._authenticate()
                return  # 성공 시 반환
            except STTError as e:
                last_error = e
                if attempt < AUTH_MAX_RETRIES:
                    logger.warning(
                        f"VITO 인증 실패 (시도 {attempt}/{AUTH_MAX_RETRIES}), "
                        f"{AUTH_RETRY_DELAY_SECONDS}초 후 재시도..."
                    )
                    time.sleep(AUTH_RETRY_DELAY_SECONDS)

        # 모든 재시도 실패
        logger.error(f"VITO 인증 최종 실패 ({AUTH_MAX_RETRIES}회 시도)")
        raise last_error or STTError("VITO 인증 실패")

    def _authenticate(self) -> None:
        """VITO API 인증 토큰 발급"""
        logger.info("VITO STT 인증 토큰 발급 중...")

        data = {
            "client_id": settings.vito_client_id,
            "client_secret": settings.vito_client_secret,
        }

        try:
            response = self._session.post(
                VITO_AUTH_URL,
                data=data,
                timeout=30.0,
            )
            response.raise_for_status()

            result = response.json()
            self._token = result["access_token"]

            # 토큰 유효기간 설정 (기본 6시간, API 응답에 expires_in이 있으면 사용)
            expires_in = result.get("expires_in", TOKEN_VALIDITY_HOURS * 3600)
            self._token_expiry = time.time() + expires_in

            expiry_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._token_expiry))
            logger.info(f"VITO STT 인증 성공 (만료: {expiry_time})")

        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            logger.error(f"VITO 인증 실패: {detail}")
            raise STTError(f"VITO 인증 실패: {detail}") from exc

    def _force_refresh_token(self) -> None:
        """토큰 강제 갱신 (API 요청 실패 시 호출)"""
        with self._token_lock:
            logger.info("토큰 강제 갱신 시도...")
            self._token = None
            self._token_expiry = 0
            self._authenticate_with_retry()

    def is_token_valid(self) -> bool:
        """현재 토큰 유효 여부 확인"""
        return (
            self._token is not None
            and time.time() < self._token_expiry - TOKEN_REFRESH_MARGIN_SECONDS
        )

    def get_token_info(self) -> dict[str, Any]:
        """토큰 정보 반환 (디버깅용)"""
        return {
            "has_token": self._token is not None,
            "is_valid": self.is_token_valid(),
            "expiry_timestamp": self._token_expiry,
            "expiry_datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._token_expiry)) if self._token_expiry > 0 else None,
            "remaining_seconds": max(0, self._token_expiry - time.time()) if self._token_expiry > 0 else 0,
        }

    def transcribe(
        self,
        audio: bytes | Path | BinaryIO,
        *,
        language: str = "ko",
        diarize: bool = False,
        speaker_count: Optional[int] = None,
    ) -> STTResult:
        """음성을 텍스트로 변환

        Args:
            audio: 음성 데이터 (bytes, 파일 경로, 또는 스트림)
            language: 언어 코드 (기본값: "ko")
            diarize: 화자 분리 여부
            speaker_count: 예상 화자 수 (diarize=True일 때 사용)

        Returns:
            STTResult: 인식 결과

        Raises:
            STTError: 인식 실패 시

        Note:
            토큰 만료로 인한 401 에러 발생 시 자동으로 토큰을 갱신하고 재시도합니다.
        """
        # 오디오 바이트로 변환 (재시도 시 재사용)
        audio_bytes = self._read_audio_bytes(audio)

        # 최대 2번 시도 (첫 시도 + 토큰 갱신 후 재시도)
        for attempt in range(2):
            try:
                return self._do_transcribe(
                    audio_bytes=audio_bytes,
                    language=language,
                    diarize=diarize,
                    speaker_count=speaker_count,
                )
            except STTError as e:
                # 401 Unauthorized 에러인 경우 토큰 갱신 후 재시도
                error_msg = str(e).lower()
                is_auth_error = (
                    "401" in error_msg
                    or "unauthorized" in error_msg
                    or "token" in error_msg
                    or "expired" in error_msg
                )

                if is_auth_error and attempt == 0:
                    logger.warning("토큰 만료로 인한 요청 실패, 토큰 갱신 후 재시도...")
                    self._force_refresh_token()
                    continue

                # 그 외 에러는 그대로 발생
                raise

        # 여기까지 오면 안 됨
        raise STTError("VITO STT 요청 실패: 알 수 없는 오류")

    def _do_transcribe(
        self,
        audio_bytes: bytes,
        *,
        language: str,
        diarize: bool,
        speaker_count: Optional[int],
    ) -> STTResult:
        """실제 STT 요청 수행 (내부용)"""
        self._ensure_valid_token()

        # 요청 설정
        config: dict[str, Any] = {
            "use_itn": True,  # 숫자/날짜 정규화
            "use_disfluency_filter": False,  # 불필요어 필터링 비활성화 (원본 유지)
            "use_profanity_filter": False,  # 비속어 필터링 비활성화
        }

        if language:
            config["language"] = language

        if diarize:
            config["use_diarization"] = True
            if speaker_count is not None:
                config["speaker_count"] = speaker_count
                config["min_speaker_count"] = speaker_count
                config["max_speaker_count"] = speaker_count

        # API 요청
        files = {"file": ("audio.wav", audio_bytes, "application/octet-stream")}
        data = {"config": json.dumps(config)}
        headers = {"Authorization": f"Bearer {self._token}"}

        try:
            logger.debug(f"VITO STT 요청 시작 (크기: {len(audio_bytes)} bytes)")

            response = self._session.post(
                VITO_TRANSCRIBE_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=self._timeout,
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            status_code = exc.response.status_code if exc.response is not None else None
            logger.error(f"VITO STT 요청 실패 (status={status_code}): {detail}")
            raise STTError(f"VITO STT 요청 실패 (status={status_code}): {detail}") from exc

        # 결과 처리 (비동기 작업인 경우 폴링)
        initial_payload = response.json()
        final_payload = self._resolve_final_payload(initial_payload, headers=headers)

        # 결과 파싱
        text = self._extract_text(final_payload)
        segments = self._parse_segments(final_payload)

        # text가 비어있으면 segments에서 텍스트 합치기
        if not text.strip() and segments:
            text = " ".join(seg.text for seg in segments if seg.text)

        logger.info(f"VITO STT 완료: {text[:50]}..." if len(text) > 50 else f"VITO STT 완료: {text}")

        return STTResult(
            text=text.strip(),
            language=final_payload.get("language", language),
            segments=segments,
            raw=final_payload,
        )

    def transcribe_file(self, path: str | Path, **kwargs) -> STTResult:
        """파일에서 음성 인식"""
        return self.transcribe(Path(path), **kwargs)

    def transcribe_bytes(self, data: bytes, **kwargs) -> STTResult:
        """바이트 데이터에서 음성 인식"""
        return self.transcribe(data, **kwargs)

    def transcribe_stream(self, stream: BinaryIO, **kwargs) -> STTResult:
        """스트림에서 음성 인식"""
        return self.transcribe(stream, **kwargs)

    @staticmethod
    def _read_audio_bytes(source: bytes | Path | BinaryIO) -> bytes:
        """다양한 입력을 바이트로 변환"""
        if isinstance(source, (bytes, bytearray)):
            return bytes(source)
        if isinstance(source, (str, Path)):
            return Path(source).expanduser().read_bytes()
        if hasattr(source, "read"):
            data = source.read()
            if isinstance(data, str):
                return data.encode()
            return data
        raise TypeError(f"지원하지 않는 오디오 타입: {type(source)!r}")

    def _resolve_final_payload(
        self,
        payload: dict[str, Any],
        *,
        headers: dict[str, str]
    ) -> dict[str, Any]:
        """비동기 작업 결과 폴링"""
        # 이미 결과가 있으면 반환
        if payload.get("text") or payload.get("segments") or payload.get("results"):
            return payload

        # 작업 ID가 있으면 폴링
        job_id = payload.get("id")
        if not job_id:
            return payload

        url = f"{VITO_TRANSCRIBE_URL}/{job_id}"
        deadline = time.time() + 60  # 최대 60초 대기

        while True:
            try:
                resp = self._session.get(url, headers=headers, timeout=self._timeout)
                resp.raise_for_status()
                body = resp.json()
            except requests.RequestException as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                raise STTError(f"VITO STT 결과 조회 실패: {detail}") from exc

            status = body.get("status")
            if status in (None, "completed", "done", "finished", "ok", "succeeded", "transcribed"):
                return body
            if status in ("failed", "error"):
                raise STTError(f"VITO STT 작업 실패: {body}")
            if time.time() > deadline:
                raise STTError("VITO STT 결과 대기 시간 초과 (60초)")

            time.sleep(1.0)

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        """결과에서 텍스트 추출"""
        return (
            payload.get("text")
            or (payload.get("results") or {}).get("text")
            or (payload.get("results") or {}).get("transcript")
            or ""
        )

    @staticmethod
    def _parse_segments(payload: dict[str, Any]) -> list[STTSegment]:
        """결과에서 세그먼트 파싱"""
        raw_segments = (
            payload.get("segments")
            or (payload.get("results") or {}).get("segments")
            or (payload.get("results") or {}).get("utterances")
            or payload.get("utterances")
            or []
        )

        segments: list[STTSegment] = []
        for item in raw_segments:
            text = (item.get("text") or item.get("msg") or item.get("message") or "").strip()

            # 시간 정보 추출
            start = item.get("start") or item.get("start_time") or item.get("start_at") or item.get("stime")
            end = item.get("end") or item.get("end_time") or item.get("end_at") or item.get("etime")

            # VITO는 밀리초 단위로 반환하므로 초 단위로 변환
            start_sec = float(start) / 1000 if start is not None else None
            end_sec = float(end) / 1000 if end is not None else None

            confidence = item.get("confidence") or item.get("probability") or item.get("prob")
            speaker = item.get("speaker") or item.get("spk") or item.get("speaker_id")

            segments.append(STTSegment(
                text=text,
                start=start_sec,
                end=end_sec,
                confidence=float(confidence) if confidence is not None else None,
                speaker=str(speaker) if speaker is not None else None,
            ))

        return segments
