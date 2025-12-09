"""
Google Cloud Text-to-Speech client.

Uses the public REST API (`text:synthesize`) with API key auth. Set
`GEM_API_KEY` in the environment or pass it directly. Defaults to MP3
output; adjust `audio_encoding`/`voice_name`/`language_code` as needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

import base64
import os
import requests


GOOGLE_TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"


class TTSError(RuntimeError):
    """Raised when the TTS request fails."""


@dataclass(slots=True)
class TTSResult:
    """Result for synthesized speech."""

    audio: bytes
    voice: str
    mime_type: str
    text: str
    raw: dict[str, object] | None = None


class TTSEngine(Protocol):
    """Interface that TTS engines must implement."""

    def synthesize(self, text: str, *, voice: str, format: str) -> TTSResult: ...


class GoogleTTSEngine:
    """
    Wrapper around Google Cloud Text-to-Speech.

    Auth flow:
    - If `credentials_path` (or GOOGLE_APPLICATION_CREDENTIALS) is provided, use service account JSON to fetch a bearer token.
    - Else fallback to API Key (GEM_API_KEY).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        credentials_path: str | None = None,
        scopes: list[str] | None = None,
        endpoint: str = GOOGLE_TTS_ENDPOINT,
        language_code: str = "ko-KR",
        voice_name: str = "ko-KR-Neural2-B",
        speaking_rate: float | None = None,
        pitch: float | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key or os.getenv("GEM_API_KEY")
        self._credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._scopes = scopes or ["https://www.googleapis.com/auth/cloud-platform"]
        self._credentials = None
        self._token_request = None

        if self._credentials_path:
            try:
                from google.oauth2 import service_account  # type: ignore
                from google.auth.transport.requests import Request  # type: ignore
            except ImportError as exc:  # pragma: no cover - dependency hint
                raise ImportError(
                    "google-auth is required for service account authentication. Install with `pip install google-auth`."
                ) from exc

            self._credentials = service_account.Credentials.from_service_account_file(
                self._credentials_path, scopes=self._scopes
            )
            self._token_request = Request()

        if not self._api_key and not self._credentials:
            raise ValueError("api_key (GEM_API_KEY) or service account credentials are required")

        self._endpoint = endpoint
        self._language_code = language_code
        self._voice_name = voice_name
        self._speaking_rate = speaking_rate
        self._pitch = pitch
        self._timeout = timeout

    def synthesize(self, text: str, *, voice: str | None = None, format: str = "mp3") -> TTSResult:
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": self._language_code,
                "name": voice or self._voice_name,
            },
            "audioConfig": {
                "audioEncoding": format.upper(),
            },
        }
        if self._speaking_rate is not None:
            payload["audioConfig"]["speakingRate"] = self._speaking_rate
        if self._pitch is not None:
            payload["audioConfig"]["pitch"] = self._pitch

        headers, params = self._build_auth()

        try:
            response = requests.post(
                self._endpoint,
                params=params,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise TTSError(f"Google TTS request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json()
            except Exception:
                pass
            raise TTSError(f"Google TTS request failed [{response.status_code}]: {detail}")

        data = response.json()
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            raise TTSError("Google TTS response did not contain audioContent")
        audio_bytes = base64.b64decode(audio_b64)
        mime_type = f"audio/{format.lower()}"

        return TTSResult(
            audio=audio_bytes,
            voice=voice or self._voice_name,
            mime_type=mime_type,
            text=text,
            raw=data,
        )

    def _build_auth(self) -> tuple[dict[str, str], dict[str, str]]:
        """Return headers/params for auth depending on credentials or API key."""
        headers: dict[str, str] = {}
        params: dict[str, str] = {}

        if self._credentials:
            if not self._credentials.valid:
                # Refresh if token expired/absent.
                assert self._token_request is not None
                self._credentials.refresh(self._token_request)
            headers["Authorization"] = f"Bearer {self._credentials.token}"
        elif self._api_key:
            params["key"] = self._api_key

        return headers, params


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
