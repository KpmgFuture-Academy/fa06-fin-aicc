"""
VITO(Return Zero) STT client with optional diarization support.
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
    """Raised when the VITO transcription request fails."""


def authenticate(client_id: str, client_secret: str) -> str:
    """Obtain an access token (valid for ~6 hours)."""
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
    """Normalize various audio inputs into bytes."""
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
    raw: dict[str, Any] | None = None


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


class ReturnZeroSTTEngine:
    """VITO(Return Zero) HTTP API client."""

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = "https://openapi.vito.ai/v1/transcribe",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def transcribe(
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
                # Hint aggressively to bound diarization to the desired speaker count.
                config["min_speaker_count"] = speaker_count
                config["max_speaker_count"] = speaker_count

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
            raise VitoSTTError(f"VITO STT request failed: {detail}") from exc

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
            text = (item.get("text") or item.get("msg") or item.get("message") or "").strip()
            start = item.get("start") or item.get("start_time") or item.get("start_at") or item.get("stime")
            end = item.get("end") or item.get("end_time") or item.get("end_at") or item.get("etime")
            confidence = item.get("confidence") or item.get("probability") or item.get("prob")
            speaker = item.get("speaker") or item.get("spk") or item.get("speaker_id")
            segments.append(
                VitoTranscriptionSegment(
                    text=text,
                    start=_safe_float(start),
                    end=_safe_float(end),
                    confidence=_safe_float(confidence),
                    speaker=str(speaker) if speaker is not None else None,
                )
            )
        return segments

    def _resolve_final_payload(self, payload: dict[str, Any], *, headers: dict[str, str]) -> dict[str, Any]:
        """
        If the POST response only returns an id, poll GET /transcribe/{id}
        until the job completes or times out.
        """
        if payload.get("text") or payload.get("segments") or payload.get("results"):
            return payload

        job_id = payload.get("id")
        if not job_id:
            return payload

        url = f"{self._endpoint}/{job_id}"
        deadline = time.time() + 60
        while True:
            try:
                resp = self._session.get(url, headers=headers, timeout=self._timeout)
                resp.raise_for_status()
                body = resp.json()
            except requests.RequestException as exc:
                detail = exc.response.text if exc.response is not None else ""
                raise VitoSTTError(f"VITO STT result polling failed: {detail}") from exc

            status = body.get("status")
            if status in (None, "completed", "done", "finished", "ok", "succeeded", "transcribed"):
                return body
            if status in ("failed", "error"):
                raise VitoSTTError(f"VITO STT job failed: {body}")
            if time.time() > deadline:
                raise VitoSTTError("VITO STT result polling timeout (60s)")
            time.sleep(1.0)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class VitoSpeechToTextService:
    """High-level facade wrapping a VITO STT engine."""

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
