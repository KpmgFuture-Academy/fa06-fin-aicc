"""
VITO(Return Zero) 음성 인식 API를 다루는 STT 모듈.

HTTP 기반 API를 호출해 전사 결과를 받아오고, 다른 엔진으로 교체할 수 있도록
간단한 추상화를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Protocol

import io
import json
import time


import requests


class VitoSTTError(RuntimeError):
    """VITO API 호출이 실패했을 때 사용하는 예외."""


def authenticate(client_id: str, client_secret: str) -> str:
    """
    VITO API 인증을 통해 액세스 토큰을 발급받습니다.
    토큰 유효 기간은 6시간입니다.
    """
    url = "https://openapi.vito.ai/v1/authenticate"
    data = {"client_id": client_id, "client_secret": client_secret}
    try:
        response = requests.post(url, data=data, timeout=30.0)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else ""
        raise VitoSTTError(f"VITO 인증 실패: {detail}") from exc


def _read_audio_bytes(source: str | Path | bytes | BinaryIO) -> bytes:
    """다양한 입력을 바이너리로 통일한다."""

    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).expanduser().read_bytes()
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            return data.encode()
        return data
    raise TypeError(f"지원하지 않는 입력 타입입니다: {type(source)!r}")


@dataclass(slots=True)
class VitoTranscriptionSegment:
    """세그먼트별 텍스트 및 타임코드."""

    text: str
    start: float | None = None
    end: float | None = None
    confidence: float | None = None


@dataclass(slots=True)
class VitoTranscriptionResult:
    """전사 결과 텍스트와 세그먼트."""

    text: str
    language: str | None = None
    segments: list[VitoTranscriptionSegment] = field(default_factory=list)
    raw: dict[str, Any] | None = None


class VitoSTTEngine(Protocol):
    """엔진 구현체가 따라야 하는 최소 인터페이스."""

    def transcribe(self, audio: str | Path | bytes | BinaryIO, *, language: str | None = None) -> VitoTranscriptionResult: ...


class ReturnZeroSTTEngine:
    """VITO(Return Zero) HTTP API를 호출해 전사를 수행하는 엔진."""

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = "https://openapi.vito.ai/v1/transcribe",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key는 필수입니다.")
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def transcribe(self, audio: str | Path | bytes | BinaryIO, *, language: str | None = None) -> VitoTranscriptionResult:
        audio_bytes = _read_audio_bytes(audio)
        config: dict[str, Any] = {
            "use_itn": True,
            "use_disfluency_filter": False,
            "use_profanity_filter": False,
        }
        if language:
            config["language"] = language

        files = {
            "file": ("audio.wav", audio_bytes, "application/octet-stream"),
        }
        data: dict[str, Any] = {"config": json.dumps(config)}

        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._session.post(
                self._endpoint,
                headers=headers,
                data=data,
                files=files,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else ""
            raise VitoSTTError(f"VITO STT 요청 실패: {detail}") from exc

        initial_payload = response.json()
        final_payload = self._resolve_final_payload(initial_payload, headers=headers)

        text = (
            final_payload.get("text")
            or (final_payload.get("results") or {}).get("text")
            or (final_payload.get("results") or {}).get("transcript")
            or " ".join(seg.text for seg in self._parse_segments(final_payload))
        )
        language = final_payload.get("language", language)
        segments = self._parse_segments(final_payload)
        return VitoTranscriptionResult(
            text=text.strip(),
            language=language,
            segments=segments,
            raw=final_payload,
        )

    @staticmethod
    def _parse_segments(payload: dict[str, Any] | Iterable[dict[str, Any]]) -> list[VitoTranscriptionSegment]:
        if isinstance(payload, dict):
            raw_segments = (
                payload.get("segments")
                or (payload.get("results") or {}).get("segments")
                or (payload.get("results") or {}).get("utterances")
                or payload.get("utterances")
                or []
            )
        else:
            raw_segments = payload

        segments: list[VitoTranscriptionSegment] = []
        for item in raw_segments:
            # VITO는 utterance 필드 이름이 다를 수 있어 넓게 대응
            text = (item.get("text") or item.get("msg") or item.get("message") or "").strip()
            start = item.get("start") or item.get("start_time") or item.get("start_at") or item.get("stime")
            end = item.get("end") or item.get("end_time") or item.get("end_at") or item.get("etime")
            confidence = item.get("confidence") or item.get("probability") or item.get("prob")
            segments.append(
                VitoTranscriptionSegment(
                    text=text,
                    start=_safe_float(start),
                    end=_safe_float(end),
                    confidence=_safe_float(confidence),
                )
            )
        return segments

    def _resolve_final_payload(self, payload: dict[str, Any], *, headers: dict[str, str]) -> dict[str, Any]:
        """
        POST /transcribe 응답에 text/segments가 없고 id만 온 경우,
        GET /transcribe/{id}로 완료 상태를 폴링해 최종 결과를 반환한다.
        """
        # 바로 결과가 온 경우 그대로 사용
        if payload.get("text") or payload.get("segments") or payload.get("results"):
            return payload

        job_id = payload.get("id")
        if not job_id:
            return payload

        url = f"{self._endpoint}/{job_id}"
        deadline = time.time() + 60  # 최대 60초 대기
        while True:
            try:
                resp = self._session.get(url, headers=headers, timeout=self._timeout)
                resp.raise_for_status()
                body = resp.json()
            except requests.RequestException as exc:
                detail = exc.response.text if exc.response is not None else ""
                raise VitoSTTError(f"VITO STT 결과 조회 실패: {detail}") from exc

            status = body.get("status")
            if status in (None, "completed", "done", "finished", "ok", "succeeded", "transcribed"):
                return body
            if status in ("failed", "error"):
                raise VitoSTTError(f"VITO STT 작업 실패: {body}")
            if time.time() > deadline:
                raise VitoSTTError("VITO STT 결과 조회 타임아웃(60초)")
            time.sleep(1.0)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class VitoSpeechToTextService:
    """파일·스트림 입력을 받아 VITO 엔진으로 전사를 수행하는 서비스."""

    def __init__(self, engine: VitoSTTEngine) -> None:
        self._engine = engine

    def transcribe_file(self, path: str | Path, *, language: str | None = None) -> VitoTranscriptionResult:
        return self._engine.transcribe(Path(path), language=language)

    def transcribe_stream(self, stream: BinaryIO, *, language: str | None = None) -> VitoTranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return self._engine.transcribe(buffer.getvalue(), language=language)

    def transcribe_bytes(self, data: bytes, *, language: str | None = None) -> VitoTranscriptionResult:
        return self._engine.transcribe(data, language=language)

