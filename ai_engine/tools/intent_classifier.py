# ai_engine/tools/intent_classifier.py

"""KoBERT 의도 분류 클라이언트."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.schemas.common import IntentType


@dataclass
class IntentResult:
    """KoBERT 응답을 표준화한 데이터 구조."""

    intent: IntentType
    confidence: float
    raw_label: str
    metadata: Optional[dict] = None


def classify_intent(text: str) -> IntentResult:
    """KoBERT 모델 엔드포인트를 호출해 의도와 신뢰도를 반환한다.

    Args:
        text: 고객 발화 원문

    Returns:
        IntentResult: 표준화된 의도/신뢰도 정보

    TODO:
        - KoBERT API URL 및 인증 설정
        - HTTP 요청/응답 파싱
        - 응답 라벨을 IntentType으로 매핑
        - 오류 발생 시 fallback intent 정의
    """
    raise NotImplementedError("classify_intent() is not implemented yet.")

