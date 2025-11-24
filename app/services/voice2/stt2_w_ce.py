"""
VITO(Return Zero) STT client with diarization plus content-emotion analysis.
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


# ---------------------------
# Customer emotion analysis
# ---------------------------

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# Prompt is tuned for banking contact-center scenarios and forces a strict JSON reply.
CUSTOMER_EMOTION_SYSTEM_PROMPT = """
너는 은행 AICC의 '실시간 리스크 관리자'야.
고객의 발화를 분석해서 다음 JSON 포맷으로 무조건 답변해. 다른 말은 하지 마.

anger_score 가이드를 따라 점수를 매겨:
- 1~2: 차분/무감정, 불편 없음
- 3~4: 약한 불편/짜증 조짐, 불만 거의 없음
- 5~6: 불만/짜증 표현 시작, 톤이 높아짐, 재촉/압박 시작
- 7~8: 강한 불만·분노, 요구/압박, 공격적 어투 가능
- 9: 매우 격앙, 모욕/폭언 직전 또는 일부 포함, 강한 위협/압박
- 10: 극대노, 노골적 폭언/협박/고함, 대화 단절 직전 수준

{
  "sentiment": "Positive" | "Neutral" | "Negative",
  "anger_score": 1~10 (숫자, 10이 극대노),
  "category": "General" | "Complaint" | "Phishing" | "Sales_Interest",
  "reason": "판단 이유 한 줄 요약"
}
""".strip()


class CustomerEmotionError(RuntimeError):
    """Raised when the customer emotion analysis fails."""


@dataclass(slots=True)
class CustomerEmotionResult:
    sentiment: str | None
    anger_score: int | None
    category: str | None
    reason: str | None
    raw: dict[str, Any] | str | None = None


class CustomerEmotionClient(Protocol):
    def analyze(self, text: str) -> CustomerEmotionResult: ...


class OpenAIChatCustomerEmotionClient:
    """Thin wrapper over OpenAI chat/completions for customer-emotion analysis."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4o-mini",
        endpoint: str = OPENAI_CHAT_URL,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()

    def analyze(self, text: str) -> CustomerEmotionResult:
        if not text or not text.strip():
            raise ValueError("text is required for sentiment analysis")

        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": CUSTOMER_EMOTION_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._session.post(self._endpoint, json=payload, headers=headers, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else ""
            raise CustomerEmotionError(f"OpenAI chat request failed: {detail}") from exc

        body = response.json()
        content = (
            (body.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        parsed: dict[str, Any] | None = None
        if content:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = None

        sentiment = None
        anger_score = None
        category = None
        reason = None
        if isinstance(parsed, dict):
            sentiment = parsed.get("sentiment")
            anger_score = _safe_int(parsed.get("anger_score"))
            category = parsed.get("category")
            reason = parsed.get("reason")
        else:
            # If the model did not return JSON, surface the raw content for debugging.
            reason = content or None

        return CustomerEmotionResult(
            sentiment=sentiment,
            anger_score=anger_score,
            category=category,
            reason=reason,
            raw=parsed or content,
        )


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------
# Combined service (STT + CE)
# ---------------------------

@dataclass(slots=True)
class TranscriptionWithEmotion:
    transcription: VitoTranscriptionResult
    emotion: CustomerEmotionResult | None = None


class VitoSTTWithCustomerEmotionService:
    """
    Composite service:
    1) runs VITO STT (with diarization if requested)
    2) extracts customer-only text using speaker labels
    3) runs sentiment/risk analysis via OpenAI chat
    """

    def __init__(
        self,
        stt_engine: VitoSTTEngine,
        emotion_client: CustomerEmotionClient,
        *,
        customer_speaker: str = "1",
    ) -> None:
        self._stt_engine = stt_engine
        self._emotion_client = emotion_client
        self._default_customer_speaker = str(customer_speaker)

    def transcribe_and_analyze(
        self,
        audio: str | Path | bytes | BinaryIO,
        *,
        language: str | None = None,
        diarize: bool = True,
        speaker_count: int | None = None,
        customer_speaker: str | None = None,
    ) -> TranscriptionWithEmotion:
        transcription = self._stt_engine.transcribe(
            audio,
            language=language,
            diarize=diarize,
            speaker_count=speaker_count,
        )

        speaker_key = str(customer_speaker) if customer_speaker is not None else self._default_customer_speaker
        customer_text = _extract_customer_text(transcription, speaker_key=speaker_key)

        emotion_result: CustomerEmotionResult | None = None
        if customer_text:
            emotion_result = self._emotion_client.analyze(customer_text)

        return TranscriptionWithEmotion(transcription=transcription, emotion=emotion_result)


def _extract_customer_text(result: VitoTranscriptionResult, *, speaker_key: str) -> str:
    """
    Returns concatenated text for the given speaker. If diarization is missing
    or the target speaker is not found, falls back to the full transcript.
    """
    if not result.segments:
        return result.text

    chosen_segments = [seg.text for seg in result.segments if seg.speaker == speaker_key and seg.text]
    if chosen_segments:
        return " ".join(chosen_segments).strip()

    return result.text
