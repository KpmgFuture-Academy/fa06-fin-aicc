"""
OpenAI Whisper STT (WebSocket transport) + content-emotion analysis helper.

This mirrors the HTTP-based `app.services.voice.stt_w_ce` module but
routes STT traffic over WebSocket so streaming gateways can be used.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import json
import requests

from .stt import SpeechToTextService, TranscriptionResult


OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

# Prompt with explicit anger scale guide for consistent scoring.
CUSTOMER_EMOTION_SYSTEM_PROMPT = """
?�는 ?�??AICC??'?�시�?리스??관리자'??
고객??발화�?분석?�서 ?�음 JSON ?�맷?�로 무조�??��??? ?�른 말�? ?��? �?

anger_score 가?�드�??�라 ?�수�?매겨:
- 1~2: 차분/무감?? 불편 ?�음
- 3~4: ?�한 불편/짜증 조짐, 불만 거의 ?�음
- 5~6: 불만/짜증 ?�현 ?�작, ?�이 ?�아�? ?�촉/?�박 ?�작
- 7~8: 강한 불만·분노, ?�구/?�박, 공격???�투 가??- 9: 매우 격앙, 모욕/??�� 직전 ?�는 ?��? ?�함, 강한 ?�협/?�박
- 10: 극�??? ?�골????��/?�박/고함, ?�???�절 직전 ?��?

{
  "sentiment": "Positive" | "Neutral" | "Negative",
  "anger_score": 1~10 (?�자, 10??극�???,
  "category": "General" | "Complaint" | "Phishing" | "Sales_Interest",
  "reason": "?�단 ?�유 ??�??�약"
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
        content = ((body.get("choices") or [{}])[0].get("message", {}) or {}).get("content", "")

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


@dataclass(slots=True)
class TranscriptionWithEmotion:
    transcription: TranscriptionResult
    emotion: CustomerEmotionResult | None = None


class STTWithCustomerEmotionService:
    """
    Composite service:
    1) runs OpenAI Whisper STT (WebSocket transport)
    2) runs sentiment/risk analysis via OpenAI chat
    """

    def __init__(self, stt_service: SpeechToTextService, emotion_client: CustomerEmotionClient) -> None:
        self._stt_service = stt_service
        self._emotion_client = emotion_client

    def transcribe_and_analyze(
        self,
        audio: str | Path,
        *,
        language: str | None = None,
    ) -> TranscriptionWithEmotion:
        transcription = self._stt_service.transcribe_file(audio, language=language)

        emotion_result: CustomerEmotionResult | None = None
        if transcription.text:
            emotion_result = self._emotion_client.analyze(transcription.text)

        return TranscriptionWithEmotion(transcription=transcription, emotion=emotion_result)

