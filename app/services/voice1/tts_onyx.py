"""
텍스트를 음성으로 변환하는 TTS 모듈.

HTTP 기반 OpenAI TTS 엔진을 감싸고, 간단한 서비스 인터페이스를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
import io
import requests


OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"


class TTSError(RuntimeError):
    """TTS 요청이 실패했을 때 사용하는 예외."""


@dataclass(slots=True)
class TTSResult:
    """생성된 음성 데이터와 메타 정보."""

    audio: bytes
    voice: str
    mime_type: str
    text: str


class TTSEngine(Protocol):
    """TTS 엔진 구현체가 따라야 하는 인터페이스."""

    def synthesize(self, text: str, *, voice: str, format: str) -> TTSResult: ...


class OpenAITTSEngine:
    """OpenAI Audio/Speech API를 호출해 음성 합성을 수행하는 구현체."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "tts-1",
        endpoint: str = OPENAI_TTS_URL,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def synthesize(self, text: str, *, voice: str = "onyx", format: str = "mp3") -> TTSResult:
        payload = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "response_format": format,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._session.post(self._endpoint, json=payload, headers=headers, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else ""
            raise TTSError(f"OpenAI TTS request failed: {detail}") from exc

        audio_bytes = response.content
        mime_type = response.headers.get("Content-Type", f"audio/{format}")
        return TTSResult(audio=audio_bytes, voice=voice, mime_type=mime_type, text=text)


class TextToSpeechService:
    """애플리케이션에서 재사용하는 TTS 서비스."""

    def __init__(self, engine: TTSEngine) -> None:
        self._engine = engine

    def synthesize_to_file(
        self,
        text: str,
        path: str | Path,
        *,
        voice: str = "onyx",
        format: str = "mp3",
    ) -> Path:
        """텍스트를 음성으로 합성해 파일로 저장한다."""

        result = self._engine.synthesize(text, voice=voice, format=format)
        final_path = Path(path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(result.audio)
        return final_path

    def synthesize_to_bytes(self, text: str, *, voice: str = "onyx", format: str = "mp3") -> bytes:
        """텍스트를 음성으로 합성해 메모리 상의 바이트로 반환한다."""

        result = self._engine.synthesize(text, voice=voice, format=format)
        return result.audio

    def synthesize_to_stream(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: str = "onyx",
        format: str = "mp3",
    ) -> None:
        """텍스트를 음성으로 합성해 제공된 스트림에 직접 쓴다."""

        result = self._engine.synthesize(text, voice=voice, format=format)
        stream.write(result.audio)
