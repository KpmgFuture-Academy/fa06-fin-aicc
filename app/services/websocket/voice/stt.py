"""
WebSocket variant of the OpenAI Whisper STT client.

The HTTP version lives in `app.services.voice.stt`; this module mirrors its
public interface but streams audio over WebSocket so streaming servers (or
gateways) can deliver incremental transcripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import mimetypes
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Protocol

from app.services.websocket.common import (
    WebSocketExchangeError,
    parse_json_message,
    read_audio_bytes,
    run_coroutine,
    safe_float,
    stream_audio_over_websocket,
)


OPENAI_STT_WS_URL = "wss://api.openai.com/v1/audio/transcriptions"


class STTError(RuntimeError):
    """Raised when the transcription request fails."""


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str | None = None
    segments: list["TranscriptionSegment"] = field(default_factory=list)
    raw: dict[str, Any] | list[Any] | None = None


@dataclass(slots=True)
class TranscriptionSegment:
    text: str
    start: float | None = None
    end: float | None = None
    confidence: float | None = None


class STTEngine(Protocol):
    def transcribe(
        self,
        source: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
    ) -> TranscriptionResult:
        ...

    async def transcribe_async(
        self,
        source: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
    ) -> TranscriptionResult:
        ...


class OpenAIWhisperWebSocketSTT:
    """
    Minimal STT client that streams to a Whisper-compatible WebSocket
    endpoint. The default URL mirrors the HTTP endpoint but with `wss://`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "whisper-1",
        endpoint: str = OPENAI_STT_WS_URL,
        timeout: float = 60.0,
        chunk_size: int = 8192,
        terminal_events: tuple[str, ...] = ("final", "done", "result", "completed"),
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._chunk_size = chunk_size
        self._terminal_events = terminal_events
        self._headers = {"Authorization": f"Bearer {self._api_key}"}

    def transcribe_file(self, path: str | Path, *, language: str | None = None) -> TranscriptionResult:
        return self.transcribe(Path(path), language=language)

    def transcribe_stream(self, stream: BinaryIO, *, language: str | None = None) -> TranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return self.transcribe(buffer.getvalue(), language=language)

    def transcribe(self, audio: str | Path | bytes | BinaryIO, *, language: str | None = None) -> TranscriptionResult:
        return run_coroutine(self.transcribe_async(audio, language=language))

    async def transcribe_async(
        self,
        audio: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
    ) -> TranscriptionResult:
        audio_bytes = read_audio_bytes(audio)
        name = Path(audio).name if isinstance(audio, (str, Path)) else "audio.bin"
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"

        start_message: dict[str, Any] = {"type": "start", "model": self._model, "mime_type": mime}
        if language:
            start_message["language"] = language

        messages = await stream_audio_over_websocket(
            self._endpoint,
            headers=self._headers,
            start_message=start_message,
            stop_message={"type": "stop"},
            audio_bytes=audio_bytes,
            chunk_size=self._chunk_size,
            timeout=self._timeout,
            terminal_events=self._terminal_events,
        )
        return self._build_result(messages, language=language)

    def _build_result(self, messages: list[Any], *, language: str | None) -> TranscriptionResult:
        parsed_messages: list[Any] = []
        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []
        final_payload: dict[str, Any] | None = None

        for message in messages:
            payload = parse_json_message(message) or message
            parsed_messages.append(payload)

            if isinstance(payload, dict):
                event = str(
                    payload.get("type") or payload.get("event") or payload.get("status") or ""
                ).lower()
                if event == "error":
                    raise STTError(payload.get("error") or payload.get("message") or str(payload))

                if payload.get("segments"):
                    segments = self._parse_segments(payload["segments"])
                elif payload.get("segment"):
                    segments.append(self._parse_single_segment(payload["segment"]))

                text_value = payload.get("text") or payload.get("transcript") or payload.get("message")
                if text_value:
                    text_parts.append(str(text_value).strip())

                if event in self._terminal_events or payload.get("done") or payload.get("final"):
                    final_payload = payload
                    break

        text = ""
        if isinstance(final_payload, dict):
            text = str(final_payload.get("text") or final_payload.get("transcript") or "").strip()
        if not text:
            text = " ".join(text_parts).strip()

        language_value = language
        if isinstance(final_payload, dict):
            language_value = final_payload.get("language", language_value)

        return TranscriptionResult(
            text=text,
            language=language_value,
            segments=segments,
            raw=final_payload or parsed_messages,
        )

    @staticmethod
    def _parse_segments(raw_segments: Iterable[dict[str, Any]]) -> list[TranscriptionSegment]:
        parsed: list[TranscriptionSegment] = []
        for entry in raw_segments:
            parsed.append(
                TranscriptionSegment(
                    text=(entry.get("text") or "").strip(),
                    start=safe_float(entry.get("start")),
                    end=safe_float(entry.get("end")),
                    confidence=safe_float(entry.get("confidence")),
                )
            )
        return parsed

    @staticmethod
    def _parse_single_segment(entry: dict[str, Any]) -> TranscriptionSegment:
        return TranscriptionSegment(
            text=(entry.get("text") or "").strip(),
            start=safe_float(entry.get("start")),
            end=safe_float(entry.get("end")),
            confidence=safe_float(entry.get("confidence")),
        )


class SpeechToTextService:
    """
    High-level facade used by API routes or background jobs.
    Mirrors the HTTP version but adds async helpers for event-loop callers.
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

    async def transcribe_file_async(self, path: str | Path, *, language: str | None = None) -> TranscriptionResult:
        return await self._engine.transcribe_async(Path(path), language=language)

    async def transcribe_stream_async(
        self,
        stream: BinaryIO,
        *,
        language: str | None = None,
    ) -> TranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return await self._engine.transcribe_async(buffer.getvalue(), language=language)

    async def transcribe_bytes_async(self, data: bytes, *, language: str | None = None) -> TranscriptionResult:
        return await self._engine.transcribe_async(data, language=language)

