"""Google Cloud TTS 서비스 - 기존 OpenAI TTS와 병행 사용 가능

본 파일은 `tts_service.py`를 그대로 두고, Google TTS용 별도 서비스 클래스를 제공합니다.
엔드포인트 교체 없이 주입만 바꿔 사용할 수 있도록 OpenAI 서비스와 동일한 인터페이스를 따릅니다.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional

from google_tts.tts4 import GoogleTTSEngine, TTSError as GoogleTTSError

logger = logging.getLogger(__name__)

# 허용 포맷 (Google TTS audioEncoding에 매핑)
SUPPORTED_FORMATS = {"mp3", "ogg", "opus", "wav"}

# audioEncoding 매핑
FORMAT_TO_ENCODING = {
    "mp3": "MP3",
    "ogg": "OGG_OPUS",
    "opus": "OGG_OPUS",
    "wav": "LINEAR16",
}

# MIME 매핑
MIME_TYPES = {
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "opus": "audio/opus",
    "wav": "audio/wav",
}


class TTSError(RuntimeError):
    """TTS 처리 중 발생하는 예외"""
    pass


@dataclass
class TTSResult:
    """TTS 결과"""
    audio: bytes
    voice: str
    format: str
    text: str
    mime_type: str


class AICCGoogleTTSService:
    """AICC용 Google TTS 서비스 (싱글톤)

    특징:
    - Google Cloud Text-to-Speech REST API 사용 (API Key 또는 서비스 계정)
    - OpenAI TTS 서비스와 동일한 메서드 시그니처 제공
    """

    _instance: Optional["AICCGoogleTTSService"] = None
    MAX_TEXT_LENGTH = 4096

    def __init__(self):
        """직접 생성하지 말고 get_instance() 사용"""
        api_key = (
            os.getenv("GOOGLE_TTS_API_KEY")
            or os.getenv("GEM_API_KEY")
        )
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not api_key and not credentials_path:
            raise TTSError(
                "Google TTS 인증 정보가 없습니다. "
                "GOOGLE_TTS_API_KEY(GEM_API_KEY) 또는 GOOGLE_APPLICATION_CREDENTIALS를 설정하세요."
            )

        language_code = os.getenv("GOOGLE_TTS_LANGUAGE", "ko-KR")
        voice_name = os.getenv("GOOGLE_TTS_VOICE", "ko-KR-Neural2-B")
        speaking_rate = self._parse_float_env("GOOGLE_TTS_SPEAKING_RATE")
        pitch = self._parse_float_env("GOOGLE_TTS_PITCH")
        timeout = self._parse_float_env("GOOGLE_TTS_TIMEOUT") or 60.0

        self._engine = GoogleTTSEngine(
            api_key=api_key,
            credentials_path=credentials_path,
            language_code=language_code,
            voice_name=voice_name,
            speaking_rate=speaking_rate,
            pitch=pitch,
            timeout=timeout,
        )
        self._default_voice = voice_name
        self._timeout = timeout

        logger.info(
            "Google TTS 초기화 완료 (voice: %s, lang: %s, timeout: %ss)",
            voice_name,
            language_code,
            timeout,
        )

    @classmethod
    def get_instance(cls) -> "AICCGoogleTTSService":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 리셋 (테스트용)"""
        cls._instance = None

    def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> bytes:
        """텍스트를 음성으로 변환"""
        if not text or not text.strip():
            raise TTSError("텍스트가 비어있습니다.")
        if len(text) > self.MAX_TEXT_LENGTH:
            raise TTSError(f"텍스트가 너무 깁니다. (최대 {self.MAX_TEXT_LENGTH}자, 현재 {len(text)}자)")

        fmt = format.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise TTSError(f"지원하지 않는 포맷: {format}. 지원: {SUPPORTED_FORMATS}")

        voice_name = voice or self._default_voice
        encoding = FORMAT_TO_ENCODING.get(fmt, fmt.upper())

        try:
            result = self._engine.synthesize(text, voice=voice_name, format=encoding)
        except GoogleTTSError as exc:
            raise TTSError(f"Google TTS 요청 실패: {exc}") from exc

        logger.info("Google TTS 완료 (크기: %d bytes, voice: %s)", len(result.audio), voice_name)
        return result.audio

    def synthesize_full(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> TTSResult:
        voice_name = voice or self._default_voice
        audio_bytes = self.synthesize(text, voice=voice_name, format=format)

        fmt = format.lower()
        mime_type = MIME_TYPES.get(fmt, f"audio/{fmt}")

        return TTSResult(
            audio=audio_bytes,
            voice=voice_name,
            format=fmt,
            text=text,
            mime_type=mime_type,
        )

    def synthesize_to_file(
        self,
        text: str,
        path: str | Path,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> Path:
        audio_bytes = self.synthesize(text, voice=voice, format=format)
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(audio_bytes)
        logger.info("TTS 결과 저장: %s", file_path)
        return file_path

    def synthesize_to_stream(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> int:
        audio_bytes = self.synthesize(text, voice=voice, format=format)
        stream.write(audio_bytes)
        return len(audio_bytes)

    def synthesize_chunked(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        format: str = "mp3",
        max_chunk_length: int = 1000,
    ) -> list[bytes]:
        """긴 텍스트를 청크로 나누어 음성 변환"""
        chunks = self._split_text(text, max_chunk_length)
        results: list[bytes] = []

        for i, chunk in enumerate(chunks):
            logger.debug("Google TTS 청크 %d/%d 처리 중...", i + 1, len(chunks))
            audio = self.synthesize(chunk, voice=voice, format=format)
            results.append(audio)

        return results

    @staticmethod
    def _split_text(text: str, max_length: int) -> list[str]:
        """텍스트를 문장 단위로 분할"""
        sentence_endings = (".", "!", "?", "。", "！", "？")

        chunks: list[str] = []
        current_chunk = ""

        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in sentence_endings:
                sentences.append(current_sentence.strip())
                current_sentence = ""

        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                if len(sentence) > max_length:
                    for i in range(0, len(sentence), max_length):
                        chunks.append(sentence[i:i + max_length])
                    current_chunk = ""
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [text]

    @property
    def default_voice(self) -> str:
        return self._default_voice

    @staticmethod
    def _parse_float_env(name: str) -> Optional[float]:
        value = os.getenv(name)
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            logger.warning("환경변수 %s 값을 float으로 변환할 수 없습니다: %s", name, value)
            return None


