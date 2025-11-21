"""
(설명) 음성 서비스용 Speech-to-Text 모듈.

OpenAI Whisper HTTP 엔드포인트에 대한 얇은 래퍼와 최소한의 추상화를 제공해,
향후 다른 엔진을 쉽게 교체할 수 있도록 설계되었다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import mimetypes
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Protocol

import io

import requests

OPENAI_STT_URL = "https://api.openai.com/v1/audio/transcriptions"


class STTError(RuntimeError):
    """Raised when the transcription request fails."""


def _read_audio_bytes(source: str | Path | bytes | BinaryIO) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).expanduser().read_bytes()
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            return data.encode()
        return data
    raise TypeError(f"Unsupported audio source type: {type(source)!r}")


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str | None = None
    segments: list["TranscriptionSegment"] = field(default_factory=list)
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class TranscriptionSegment:
    text: str
    start: float | None = None
    end: float | None = None
    confidence: float | None = None


class STTEngine(Protocol):
    def transcribe(self, source: str | Path | bytes | BinaryIO, *, language: str | None = None) -> TranscriptionResult:
        ...


class OpenAIWhisperSTT:
    """
    Minimal STT client that hits the OpenAI Whisper transcription endpoint.

    Parameters
    ----------
    api_key:
        OpenAI API key. Pass it explicitly rather than relying on env vars so
        callers can manage credentials however they like.
    model:
        Which Whisper deployment to call. Defaults to `gpt-4o-mini-transcribe`
        which is the most widely available streaming-ready option at the time
        of writing.
    """

    def __init__(
        self,
        api_key: str,
        *,
        # Default to whisper-1 to get verbose_json (segments/timestamps) support.
        model: str = "whisper-1",
        endpoint: str = OPENAI_STT_URL,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def transcribe_file(self, path: str | Path, *, language: str | None = None) -> TranscriptionResult:
        return self.transcribe(Path(path), language=language)

    def transcribe_stream(self, stream: BinaryIO, *, language: str | None = None) -> TranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return self.transcribe(buffer.getvalue(), language=language)

    def transcribe(self, audio: str | Path | bytes | BinaryIO, *, language: str | None = None) -> TranscriptionResult:
        audio_bytes = _read_audio_bytes(audio)
        name = Path(audio).name if isinstance(audio, (str, Path)) else "audio.bin"
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        files = {"file": (name, audio_bytes, mime)}
        data: dict[str, Any] = {
            "model": self._model,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language

        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._session.post(
                self._endpoint,
                data=data,
                files=files,
                timeout=self._timeout,
                headers=headers,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else ""
            raise STTError(f"OpenAI Whisper request failed: {detail}") from exc

        payload = response.json()
        segments = self._parse_segments(payload.get("segments") or [])
        text = payload.get("text") or " ".join(seg.text for seg in segments)
        language = payload.get("language", language)
        return TranscriptionResult(text=text.strip(), language=language, segments=segments, raw=payload)

    @staticmethod
    def _parse_segments(raw_segments: Iterable[dict[str, Any]]) -> list[TranscriptionSegment]:
        parsed: list[TranscriptionSegment] = []
        for entry in raw_segments:
            parsed.append(
                TranscriptionSegment(
                    text=(entry.get("text") or "").strip(),
                    start=_safe_float(entry.get("start")),
                    end=_safe_float(entry.get("end")),
                    confidence=_safe_float(entry.get("confidence")),
                )
            )
        return parsed


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class SpeechToTextService:
    """
    High-level facade used by API routes or background jobs.

    Example
    -------
        engine = OpenAIWhisperSTT(api_key="<secret>")
        stt = SpeechToTextService(engine)
        result = stt.transcribe_file("call.mp3")
        print(result.text)
    """

    def __init__(self, engine: STTEngine) -> None:
        self._engine = engine

    def transcribe_file(self, path: str | Path, *, language: str | None = None) -> TranscriptionResult:
        return self._engine.transcribe(Path(path), language=language)

    def transcribe_stream(self, stream: BinaryIO, *, language: str | None = None) -> TranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return self._engine.transcribe(buffer.getvalue(), language=language)

    def transcribe_bytes(self, data: bytes, *, language: str | None = None) -> TranscriptionResult:
        return self._engine.transcribe(data, language=language)
