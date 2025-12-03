"""
VITO(Return Zero) STT client that streams audio over WebSocket.

This mirrors `app.services.voice2.stt2` but replaces the HTTP POST + poll
flow with a WebSocket round-trip to a streaming gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Protocol

import io
import json
import time

import requests

from app.services.websocket.common import (
    WebSocketExchangeError,
    parse_json_message,
    read_audio_bytes,
    run_coroutine,
    safe_float,
    stream_audio_over_websocket,
)


class VitoSTTError(RuntimeError):
    """Raised when the VITO transcription request fails."""


def authenticate(client_id: str, client_secret: str) -> str:
    """Obtain an access token (valid for ~6 hours) via the HTTP auth API."""
    url = "https://openapi.vito.ai/v1/authenticate"
    data = {"client_id": client_id, "client_secret": client_secret}
    try:
        response = requests.post(url, data=data, timeout=30.0)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as exc:
        detail = exc.response.text if exc.response is not None else ""
        raise VitoSTTError(f"VITO auth failed: {detail}") from exc


def _read_audio_bytes(source: str | Path | bytes | BinaryIO) -> bytes:
    """Keep a dedicated helper to mirror the HTTP implementation signature."""
    return read_audio_bytes(source)


@dataclass(slots=True)
class VitoTranscriptionSegment:
    text: str
    start: float | None = None
    end: float | None = None
    confidence: float | None = None
    speaker: str | None = None


@dataclass(slots=True)
class VitoTranscriptionResult:
    text: str
    language: str | None = None
    segments: list[VitoTranscriptionSegment] = field(default_factory=list)
    raw: dict[str, Any] | list[Any] | None = None


class VitoSTTEngine(Protocol):
    def transcribe(
        self,
        audio: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        ...

    async def transcribe_async(
        self,
        audio: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        ...


class ReturnZeroWebSocketSTTEngine:
    """VITO(Return Zero) WebSocket API client."""

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = "wss://openapi.vito.ai/v1/transcribe",
        timeout: float = 60.0,
        chunk_size: int = 8192,
        terminal_events: tuple[str, ...] = ("final", "done", "result", "completed"),
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._chunk_size = chunk_size
        self._terminal_events = terminal_events
        self._headers = {"Authorization": f"Bearer {self._api_key}"}

    def transcribe(
        self,
        audio: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        return run_coroutine(
            self.transcribe_async(audio, language=language, diarize=diarize, speaker_count=speaker_count)
        )

    async def transcribe_async(
        self,
        audio: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        audio_bytes = _read_audio_bytes(audio)

        config: dict[str, Any] = {
            "use_itn": True,
            "use_disfluency_filter": False,
            "use_profanity_filter": False,
        }
        if language:
            config["language"] = language
        if diarize:
            config["use_diarization"] = True
            if speaker_count is not None:
                config["speaker_count"] = speaker_count
                config["min_speaker_count"] = speaker_count
                config["max_speaker_count"] = speaker_count

        start_message = {"type": "start", "config": config}

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

    def _build_result(self, messages: list[Any], *, language: str | None) -> VitoTranscriptionResult:
        parsed_messages: list[Any] = []
        segments: list[VitoTranscriptionSegment] = []
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
                    raise VitoSTTError(payload.get("error") or payload.get("message") or str(payload))

                raw_segments = (
                    payload.get("segments")
                    or (payload.get("results") or {}).get("segments")
                    or (payload.get("results") or {}).get("utterances")
                    or payload.get("utterances")
                    or payload.get("segment")
                )
                if raw_segments:
                    segments = self._parse_segments(raw_segments)

                text_value = (
                    payload.get("text")
                    or (payload.get("results") or {}).get("text")
                    or (payload.get("results") or {}).get("transcript")
                    or payload.get("message")
                )
                if text_value:
                    text_parts.append(str(text_value).strip())

                if event in self._terminal_events or payload.get("done") or payload.get("final"):
                    final_payload = payload
                    break

        text = ""
        if isinstance(final_payload, dict):
            text = (
                final_payload.get("text")
                or (final_payload.get("results") or {}).get("text")
                or (final_payload.get("results") or {}).get("transcript")
                or ""
            ).strip()
        if not text:
            text = " ".join(text_parts).strip()

        language_value = language
        if isinstance(final_payload, dict):
            language_value = final_payload.get("language", language_value)

        return VitoTranscriptionResult(
            text=text,
            language=language_value,
            segments=segments,
            raw=final_payload or parsed_messages,
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
            text = (item.get("text") or item.get("msg") or item.get("message") or "").strip()
            start = item.get("start") or item.get("start_time") or item.get("start_at") or item.get("stime")
            end = item.get("end") or item.get("end_time") or item.get("end_at") or item.get("etime")
            confidence = item.get("confidence") or item.get("probability") or item.get("prob")
            speaker = item.get("speaker") or item.get("spk") or item.get("speaker_id")
            segments.append(
                VitoTranscriptionSegment(
                    text=text,
                    start=safe_float(start),
                    end=safe_float(end),
                    confidence=safe_float(confidence),
                    speaker=str(speaker) if speaker is not None else None,
                )
            )
        return segments


class VitoSpeechToTextService:
    """High-level facade wrapping a VITO WebSocket STT engine."""

    def __init__(self, engine: VitoSTTEngine) -> None:
        self._engine = engine

    def transcribe_file(
        self,
        path: str | Path,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        return self._engine.transcribe(Path(path), language=language, diarize=diarize, speaker_count=speaker_count)

    def transcribe_stream(
        self,
        stream: BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return self._engine.transcribe(buffer.getvalue(), language=language, diarize=diarize, speaker_count=speaker_count)

    def transcribe_bytes(
        self,
        data: bytes,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        return self._engine.transcribe(data, language=language, diarize=diarize, speaker_count=speaker_count)

    async def transcribe_file_async(
        self,
        path: str | Path,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        return await self._engine.transcribe_async(
            Path(path),
            language=language,
            diarize=diarize,
            speaker_count=speaker_count,
        )

    async def transcribe_stream_async(
        self,
        stream: BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return await self._engine.transcribe_async(
            buffer.getvalue(),
            language=language,
            diarize=diarize,
            speaker_count=speaker_count,
        )

    async def transcribe_bytes_async(
        self,
        data: bytes,
        *,
        language: str | None = None,
        diarize: bool = False,
        speaker_count: int | None = None,
    ) -> VitoTranscriptionResult:
        return await self._engine.transcribe_async(data, language=language, diarize=diarize, speaker_count=speaker_count)

