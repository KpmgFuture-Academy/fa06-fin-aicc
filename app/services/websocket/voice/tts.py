"""
WebSocket variant of the OpenAI TTS client.

The HTTP version lives in `app.services.voice.tts`; this mirrors the public
interface but streams over WebSocket so gateways that return audio chunks
can be used without touching the HTTP code paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

import io

from app.services.websocket.common import (
    WebSocketExchangeError,
    parse_json_message,
    run_coroutine,
    stream_audio_over_websocket,
)


OPENAI_TTS_WS_URL = "wss://api.openai.com/v1/audio/speech"


class TTSError(RuntimeError):
    """Raised when the TTS request fails."""


@dataclass(slots=True)
class TTSResult:
    """Result for synthesized speech."""

    audio: bytes
    voice: str
    mime_type: str
    text: str
    raw: list[object] | dict[str, object] | None = None


class TTSEngine(Protocol):
    """Interface that TTS engines must implement."""

    def synthesize(self, text: str, *, voice: str, format: str) -> TTSResult: ...

    async def synthesize_async(self, text: str, *, voice: str, format: str) -> TTSResult: ...


class OpenAITTSWebSocketEngine:
    """
    Minimal TTS client that streams to an OpenAI-compatible WebSocket endpoint.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "tts-1",
        endpoint: str = OPENAI_TTS_WS_URL,
        timeout: float = 60.0,
        terminal_events: tuple[str, ...] = ("final", "done", "result", "completed"),
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._terminal_events = terminal_events
        self._headers = {"Authorization": f"Bearer {self._api_key}"}

    def synthesize(self, text: str, *, voice: str = "alloy", format: str = "mp3") -> TTSResult:
        return run_coroutine(self.synthesize_async(text, voice=voice, format=format))

    async def synthesize_async(self, text: str, *, voice: str = "alloy", format: str = "mp3") -> TTSResult:
        start_message: dict[str, str] = {
            "type": "start",
            "model": self._model,
            "voice": voice,
            "response_format": format,
            "input": text,
        }
        # No audio upload for TTS; pass an empty payload and rely on start/stop.
        messages = await stream_audio_over_websocket(
            self._endpoint,
            headers=self._headers,
            start_message=start_message,
            stop_message={"type": "stop"},
            audio_bytes=b"",
            chunk_size=1,  # not used, but keeps the helper happy
            timeout=self._timeout,
            terminal_events=self._terminal_events,
        )
        return self._build_result(messages, text=text, voice=voice, response_format=format)

    def _build_result(self, messages: list[object], *, text: str, voice: str, response_format: str) -> TTSResult:
        parsed_messages: list[object] = []
        audio_chunks: list[bytes] = []
        final_payload: dict[str, object] | None = None

        for message in messages:
            payload = parse_json_message(message) or message
            parsed_messages.append(payload)

            if isinstance(payload, dict):
                event = str(
                    payload.get("type") or payload.get("event") or payload.get("status") or ""
                ).lower()
                if event == "error":
                    raise TTSError(payload.get("error") or payload.get("message") or str(payload))

                if event in self._terminal_events or payload.get("done") or payload.get("final"):
                    final_payload = payload
                    break
            elif isinstance(payload, (bytes, bytearray)):
                audio_chunks.append(bytes(payload))

        audio = b"".join(audio_chunks)
        mime_type = f"audio/{response_format}"
        if isinstance(final_payload, dict):
            mime_type = str(final_payload.get("content_type") or final_payload.get("mime_type") or mime_type)

        return TTSResult(audio=audio, voice=voice, mime_type=mime_type, text=text, raw=final_payload or parsed_messages)


class TextToSpeechService:
    """High-level facade used by API routes or background jobs."""

    def __init__(self, engine: TTSEngine) -> None:
        self._engine = engine

    def synthesize_to_file(
        self,
        text: str,
        path: str | Path,
        *,
        voice: str = "alloy",
        format: str = "mp3",
    ) -> Path:
        result = self._engine.synthesize(text, voice=voice, format=format)
        final_path = Path(path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(result.audio)
        return final_path

    def synthesize_to_bytes(self, text: str, *, voice: str = "alloy", format: str = "mp3") -> bytes:
        result = self._engine.synthesize(text, voice=voice, format=format)
        return result.audio

    def synthesize_to_stream(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: str = "alloy",
        format: str = "mp3",
    ) -> None:
        result = self._engine.synthesize(text, voice=voice, format=format)
        stream.write(result.audio)

    async def synthesize_to_file_async(
        self,
        text: str,
        path: str | Path,
        *,
        voice: str = "alloy",
        format: str = "mp3",
    ) -> Path:
        result = await self._engine.synthesize_async(text, voice=voice, format=format)
        final_path = Path(path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(result.audio)
        return final_path

    async def synthesize_to_bytes_async(self, text: str, *, voice: str = "alloy", format: str = "mp3") -> bytes:
        result = await self._engine.synthesize_async(text, voice=voice, format=format)
        return result.audio

    async def synthesize_to_stream_async(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: str = "alloy",
        format: str = "mp3",
    ) -> None:
        result = await self._engine.synthesize_async(text, voice=voice, format=format)
        stream.write(result.audio)
