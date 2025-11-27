"""의도 분류 Tool: Hana Card 모델을 호출하여 고객 메시지의 문맥 의도를 분류합니다."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from langchain_core.tools import tool
from ai_engine.ingestion.bert_financial_intent_classifier.scripts.inference import (
    IntentClassifier,
)

logger = logging.getLogger(__name__)


@tool
def classify_intent(user_message: str) -> str:
    """Hana Card 모델을 사용하여 고객 메시지의 문맥 의도를 분류합니다.
    
    문맥 의도는 질문의 주제나 도메인을 나타냅니다 (예: 결제일 안내/변경/취소, 한도 안내 등).
    감정이나 요청 타입이 아니라 문맥 그 자체의 의도를 분류합니다.
    
    Args:
        user_message: 고객이 입력한 메시지
        
    Returns:
        문맥 의도 분류 결과 문자열 (예: "결제일 안내/변경/취소", "한도 안내", "포인트/마일리지 안내" 등)
        
    Examples:
        classify_intent("결제일 변경하고 싶어요") -> "결제일 안내/변경/취소"
        classify_intent("카드 한도 확인") -> "한도 안내"
        classify_intent("포인트 확인하고 싶습니다") -> "포인트/마일리지 안내"
    """
    classifier = _get_classifier()
    if classifier is None:
        raise RuntimeError(
            "Hana Card intent classifier is not available. "
            "모델이 올바른 위치에 있는지 확인하세요: fa06-fin-aicc/models/hana_card_model"
        )

    try:
        intent, confidence = classifier.predict_single(user_message)
        logger.debug("Intent classified via Hana Card model: %s (%.2f)", intent, confidence)
        return intent
    except Exception as exc:  # pragma: no cover - 방어적 처리
        logger.error("IntentClassifier inference failed: %s", exc, exc_info=True)
        raise


# Tool 인스턴스 생성
intent_classification_tool = classify_intent


@lru_cache(maxsize=1)
def _get_classifier() -> Optional[IntentClassifier]:
    """지연 로딩으로 Hana Card 분류기를 초기화한다."""
    try:
        logger.info("Loading Hana Card intent classifier...")
        return IntentClassifier()
    except FileNotFoundError as exc:
        logger.error(
            "Hana Card intent model not found: %s\n"
            "Expected path: fa06-fin-aicc/models/hana_card_model\n"
            "모델이 올바른 위치에 있는지 확인하세요.",
            exc,
        )
    except Exception as exc:  # pragma: no cover - 초기화 예외
        logger.error("Failed to initialize IntentClassifier: %s", exc, exc_info=True)
    return None


# 키워드 기반 fallback 함수 - 사용하지 않음 (모델이 없으면 예외 발생)
# def _keyword_based_classify(user_message: str) -> str:
#     """모델 사용이 불가능할 때 사용하는 키워드 기반 fallback."""
#     user_message_lower = user_message.lower()
#
#     if any(keyword in user_message_lower for keyword in ["대출", "대출금리", "대출금액", "대출한도"]):
#         if any(keyword in user_message_lower for keyword in ["상환", "갚", "반환", "변제"]):
#             return "대출 상환"
#         return "대출"
#
#     if any(keyword in user_message_lower for keyword in ["예금", "예금금리", "예금이자", "정기예금", "적금"]):
#         return "예금"
#
#     if any(keyword in user_message_lower for keyword in ["카드", "신용카드", "체크카드"]):
#         return "카드 상품 문의"
#
#     if any(keyword in user_message_lower for keyword in ["상담", "상담사", "상담원", "직원"]):
#         return "상담"
#
#     return "일반 문의"
