"""
HTTP variant for Humelo/Hume TTS (``humelo`` model).

Mirrors the shape of ``app.services.websocket.voice.tts`` but calls an
HTTP endpoint instead of a WebSocket stream. If the upstream service
exposes a different URL, set ``HUME_TTS_HTTP_URL`` in your environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol

import asyncio
import os
import base64
import requests

# Default HTTP endpoint for Humelo/Hume TTS. Override with env if needed.
HUME_TTS_HTTP_URL = os.getenv("HUME_TTS_HTTP_URL", "https://prosody-api.humelo.works/api/v1/dive/stream")


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


class HumeloTTSHttpEngine:
    """
    Minimal TTS client that posts to the Humelo/Hume HTTP endpoint.
    """

    def __init__(
        self,
        api_key: str,
        *,
        voice_id: str,
        model: str = "humelo",
        endpoint: str = HUME_TTS_HTTP_URL,
        language: str = "ko",
        emotion: str = "neutral",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if not voice_id:
            raise ValueError("voice_id is required")
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._language = language
        self._emotion = emotion
        self._endpoint = endpoint
        self._timeout = timeout
        # Humelo docs show X-API-Key; adjust if your service expects Bearer instead.
        self._headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
        }

    def synthesize(self, text: str, *, voice: str | None = None, format: str = "mp3") -> TTSResult:
        return self._synthesize_sync(text=text, voice=voice or self._voice_id, format=format)

    async def synthesize_async(self, text: str, *, voice: str | None = None, format: str = "mp3") -> TTSResult:
        return await asyncio.to_thread(self._synthesize_sync, text, voice or self._voice_id, format)

    def _build_payload(self, *, text: str, voice: str, response_format: str) -> dict[str, Any]:
        return {
            "model": self._model,
            "voiceId": voice,
            "voiceName": voice,  # Some Humelo variants expect voiceName
            "text": text,  # Humelo HTTP API expects this key
            "input": text,  # Backward compatibility / alternate key
            "language": self._language,
            "emotion": self._emotion,
            "response_format": response_format,
        }

    def _synthesize_sync(self, text: str, voice: str, format: str) -> TTSResult:
        payload = self._build_payload(text=text, voice=voice, response_format=format)
        try:
            response = requests.post(
                self._endpoint,
                headers=self._headers,
                json=payload,
                timeout=self._timeout,
                stream=True,
            )
        except requests.RequestException as exc:  # pragma: no cover - network
            raise TTSError(f"Humelo TTS request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = None
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise TTSError(f"Humelo TTS request failed [{response.status_code}]: {detail}")

        content_type = response.headers.get("Content-Type", "")
        audio_bytes: bytes | None = None
        raw_payload: dict[str, Any] | None = None

        if content_type.startswith("audio/"):
            audio_bytes = response.content
        else:
            # Try JSON with audio_url or base64 content
            try:
                data = response.json()
                raw_payload = data if isinstance(data, dict) else None
            except ValueError:
                data = None

            if isinstance(data, dict):
                audio_url = data.get("audio_url") or data.get("url")
                if audio_url:
                    audio_bytes = self._download_audio(audio_url)
                    content_type = response.headers.get("Content-Type", f"audio/{format}")
                else:
                    audio_b64 = data.get("audio_base64") or data.get("audio")
                    if isinstance(audio_b64, str):
                        audio_bytes = base64.b64decode(audio_b64)
                        content_type = data.get("content_type", f"audio/{format}")

        if audio_bytes is None:
            raise TTSError("Humelo TTS response did not contain audio data.")

        return TTSResult(
            audio=audio_bytes,
            voice=voice,
            mime_type=content_type or f"audio/{format}",
            text=text,
            raw=raw_payload,
        )

    def _download_audio(self, url: str) -> bytes:
        try:
            resp = requests.get(url, timeout=self._timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:  # pragma: no cover - network
            raise TTSError(f"Failed to download audio from URL: {url}") from exc


class TextToSpeechService:
    """High-level facade used by API routes or background jobs."""

    def __init__(self, engine: TTSEngine) -> None:
        self._engine = engine

    def synthesize_to_file(
        self,
        text: str,
        path: str | Path,
        *,
        voice: str | None = None,
        format: str = "mp3",
    ) -> Path:
        result = self._engine.synthesize(text, voice=voice or "", format=format)
        final_path = Path(path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(result.audio)
        return final_path

    def synthesize_to_bytes(self, text: str, *, voice: str | None = None, format: str = "mp3") -> bytes:
        result = self._engine.synthesize(text, voice=voice or "", format=format)
        return result.audio

    def synthesize_to_stream(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: str | None = None,
        format: str = "mp3",
    ) -> None:
        result = self._engine.synthesize(text, voice=voice or "", format=format)
        stream.write(result.audio)

    async def synthesize_to_file_async(
        self,
        text: str,
        path: str | Path,
        *,
        voice: str | None = None,
        format: str = "mp3",
    ) -> Path:
        result = await self._engine.synthesize_async(text, voice=voice or "", format=format)
        final_path = Path(path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(result.audio)
        return final_path

    async def synthesize_to_bytes_async(self, text: str, *, voice: str | None = None, format: str = "mp3") -> bytes:
        result = await self._engine.synthesize_async(text, voice=voice or "", format=format)
        return result.audio

    async def synthesize_to_stream_async(
        self,
        text: str,
        stream: BinaryIO,
        *,
        voice: str | None = None,
        format: str = "mp3",
    ) -> None:
        result = await self._engine.synthesize_async(text, voice=voice or "", format=format)
        stream.write(result.audio)
