"""
Speech-to-text service scaffolding used by the AICC voice pipeline.

The implementation below focuses on providing a clean abstraction that can be
re-used once the rest of the architecture is in place.  It does not ship a real
speech model, but instead exposes pluggable engines (HTTP-based or dummy) so the
team can wire their preferred provider later without touching the rest of the
codebase.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, BinaryIO, Mapping, MutableMapping, Protocol

import io
import uuid

import requests

AudioInput = BinaryIO | bytes | bytearray | memoryview | str | Path


class SpeechToTextError(RuntimeError):
    """Raised when an STT engine fails to generate a transcript."""


@dataclass(slots=True)
class STTRequestOptions:
    """Fine-grained options that can be tweaked per transcription request."""

    language: str = "ko-KR"
    enable_punctuation: bool = True
    enable_diarization: bool = False
    speaker_count: int | None = None
    acoustic_model: str | None = None
    text_normalization: str = "default"


@dataclass(slots=True)
class STTResultSegment:
    """Individual utterance metadata for downstream analysis (handover, QA, ...)."""

    start: float | None = None
    end: float | None = None
    text: str = ""
    speaker: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class STTResult:
    """Normalized transcription payload consumed by other modules."""

    text: str
    language: str
    duration: float | None = None
    segments: list[STTResultSegment] = field(default_factory=list)
    raw_response: Mapping[str, Any] | None = None


class STTEngine(Protocol):
    """Interface implemented by concrete STT engines."""

    def transcribe(self, audio: AudioInput, *, options: STTRequestOptions) -> STTResult: ...


def _read_audio_bytes(audio: AudioInput) -> bytes:
    """
    Normalize different audio sources to raw bytes.

    Accepts file paths, open file objects, or in-memory bytes so the service can
    be called from FastAPI endpoints, batch jobs, or tests alike.
    """

    if isinstance(audio, (bytes, bytearray, memoryview)):
        return bytes(audio)
    if isinstance(audio, (str, Path)):
        return Path(audio).expanduser().read_bytes()
    if hasattr(audio, "read"):
        data = audio.read()
        if isinstance(data, str):
            return data.encode()
        return data
    raise TypeError(f"Unsupported audio input type: {type(audio)!r}")


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class HTTPSTTEngine:
    """
    Generic HTTP engine that can call any speech provider exposing a JSON API.

    The remote endpoint is expected to accept a multipart/form-data payload with
    the audio file attached under ``file``.  The JSON response is mapped to the
    normalized :class:`STTResult`.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        session: requests.Session | None = None,
        extra_headers: Mapping[str, str] | None = None,
        default_mime_type: str = "audio/wav",
    ) -> None:
        if not endpoint:
            raise ValueError("endpoint is required for HTTPSTTEngine")
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._session = session or requests.Session()
        self._extra_headers = dict(extra_headers or {})
        self._default_mime_type = default_mime_type

    def transcribe(self, audio: AudioInput, *, options: STTRequestOptions) -> STTResult:
        audio_bytes = _read_audio_bytes(audio)
        files = {
            "file": (
                "speech.wav",
                audio_bytes,
                self._default_mime_type,
            )
        }
        data: MutableMapping[str, Any] = {
            "language": options.language,
            "enable_punctuation": str(options.enable_punctuation).lower(),
            "enable_diarization": str(options.enable_diarization).lower(),
            "text_normalization": options.text_normalization,
        }
        if options.speaker_count is not None:
            data["speaker_count"] = str(options.speaker_count)
        if options.acoustic_model:
            data["acoustic_model"] = options.acoustic_model

        headers = dict(self._extra_headers)
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = self._session.post(
                self._endpoint,
                data=data,
                files=files,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SpeechToTextError("HTTP STT request failed") from exc

        payload = response.json()
        return self._convert_payload(payload, fallback_language=options.language)

    @staticmethod
    def _convert_payload(payload: Mapping[str, Any], *, fallback_language: str) -> STTResult:
        segments_payload = payload.get("segments") or payload.get("results") or []
        segments: list[STTResultSegment] = []
        for segment in segments_payload:
            segments.append(
                STTResultSegment(
                    start=_float_or_none(segment.get("start")),
                    end=_float_or_none(segment.get("end")),
                    text=segment.get("text") or segment.get("transcript") or "",
                    speaker=(segment.get("speaker") or segment.get("speaker_label")),
                    confidence=_float_or_none(segment.get("confidence")),
                )
            )

        text = payload.get("text") or payload.get("transcript") or " ".join(
            segment.text for segment in segments
        )
        return STTResult(
            text=text.strip(),
            language=payload.get("language") or fallback_language,
            duration=_float_or_none(payload.get("duration")),
            segments=segments,
            raw_response=payload,
        )


class OpenAIWhisperEngine:
    """
    Convenience engine that targets the OpenAI Whisper transcription endpoint.

    It defaults to ``gpt-4o-mini-transcribe`` (the current Whisper deployment) and
    requests ``verbose_json`` responses so segment metadata is preserved.  The
    class still returns the normalized :class:`STTResult`, so switching engines
    only requires swapping constructors when wiring :class:`SpeechToTextService`.
    """

    DEFAULT_URL = "https://api.openai.com/v1/audio/transcriptions"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini-transcribe",
        base_url: str | None = None,
        timeout: float = 60.0,
        session: requests.Session | None = None,
        organization: str | None = None,
        project: str | None = None,
        response_format: str = "verbose_json",
        temperature: float | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for OpenAI Whisper")
        self._api_key = api_key
        self._model = model
        self._url = (base_url or self.DEFAULT_URL).rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()
        self._organization = organization
        self._project = project
        self._response_format = response_format
        self._temperature = temperature

    def transcribe(self, audio: AudioInput, *, options: STTRequestOptions) -> STTResult:
        audio_bytes = _read_audio_bytes(audio)
        files = {
            "file": (
                "speech.wav",
                audio_bytes,
                "audio/wav",
            )
        }
        data: MutableMapping[str, Any] = {
            "model": self._model,
            "response_format": self._response_format,
            "language": options.language,
        }
        if self._temperature is not None:
            data["temperature"] = self._temperature

        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }
        if self._organization:
            headers["OpenAI-Organization"] = self._organization
        if self._project:
            headers["OpenAI-Project"] = self._project

        try:
            response = self._session.post(
                self._url,
                data=data,
                files=files,
                timeout=self._timeout,
                headers=headers,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SpeechToTextError("OpenAI Whisper request failed") from exc

        payload = response.json()
        # Reuse the HTTP engine's converter so downstream stays identical.
        return HTTPSTTEngine._convert_payload(payload, fallback_language=options.language)


class DummySTTEngine:
    """
    Lightweight offline engine used for local development and unit tests.

    It does *not* perform real speech recognition; instead it returns a
    deterministic transcript that captures metadata so the rest of the pipeline
    can be exercised without an expensive model.
    """

    def __init__(self, *, placeholder_text: str = "음성 메시지가 수신되었습니다.") -> None:
        self._placeholder_text = placeholder_text

    def transcribe(self, audio: AudioInput, *, options: STTRequestOptions) -> STTResult:
        audio_bytes = _read_audio_bytes(audio)
        token = uuid.uuid5(uuid.NAMESPACE_OID, audio_bytes[:32].hex() if audio_bytes else "empty")
        placeholder = f"{self._placeholder_text} [{options.language}]"
        segment = STTResultSegment(
            start=0.0,
            end=None,
            text=placeholder,
            speaker="agent",
            confidence=0.0,
        )
        return STTResult(
            text=f"{placeholder} #{token.hex[:8]}",
            language=options.language,
            segments=[segment],
            raw_response={"engine": "dummy", "token": token.hex},
        )


class SpeechToTextService:
    """
    High-level facade consumed by FastAPI routes or background jobs.

    Example:
        >>> service = SpeechToTextService(OpenAIWhisperEngine(api_key="sk-...", model="gpt-4o-mini-transcribe"))
        >>> service.transcribe_file("sample.wav").text
        '안녕하세요. 상담을 진행해 보겠습니다.'
    """

    def __init__(
        self,
        engine: STTEngine | None = None,
        *,
        default_options: STTRequestOptions | None = None,
    ) -> None:
        self._engine = engine or DummySTTEngine()
        self._default_options = default_options or STTRequestOptions()

    def transcribe(self, audio: AudioInput, *, options: STTRequestOptions | None = None, **overrides: Any) -> STTResult:
        resolved = self._prepare_options(options, overrides)
        return self._engine.transcribe(audio, options=resolved)

    def transcribe_file(self, path: str | Path, **overrides: Any) -> STTResult:
        return self.transcribe(Path(path), **overrides)

    def transcribe_stream(self, stream: BinaryIO, **overrides: Any) -> STTResult:
        buffer = io.BytesIO(stream.read())
        buffer.seek(0)
        return self.transcribe(buffer.getvalue(), **overrides)

    def _prepare_options(
        self,
        options: STTRequestOptions | None,
        overrides: Mapping[str, Any],
    ) -> STTRequestOptions:
        base = options or self._default_options
        allowed = asdict(base)
        extra: dict[str, Any] = {}
        for key, value in overrides.items():
            if value is None:
                continue
            if key not in allowed:
                raise ValueError(f"Unsupported STT option override: {key}")
            extra[key] = value
        return replace(base, **extra) if extra else base

    @property
    def engine(self) -> STTEngine:
        return self._engine
