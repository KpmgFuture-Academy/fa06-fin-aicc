"""의도 분류 Tool: KoBERT 모델을 호출하여 고객 메시지의 문맥 의도를 분류합니다."""

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
    """KoBERT 모델을 사용하여 고객 메시지의 문맥 의도를 분류합니다.
    
    문맥 의도는 질문의 주제나 도메인을 나타냅니다 (예: 대출, 예금, 상담 등).
    감정이나 요청 타입이 아니라 문맥 그 자체의 의도를 분류합니다.
    
    Args:
        user_message: 고객이 입력한 메시지
        
    Returns:
        문맥 의도 분류 결과 문자열 (예: "대출", "대출 상환", "예금", "예금 상품 문의", "상담" 등)
        
    Examples:
        classify_intent("대출 금리는 얼마인가요?") -> "대출"
        classify_intent("예금 이자율이 궁금합니다") -> "예금"
        classify_intent("대출을 상환하고 싶어요") -> "대출 상환"
        classify_intent("카드 상품을 알아보고 싶습니다") -> "카드 상품 문의"
    """
    classifier = _get_classifier()
    if classifier is None:
        return _keyword_based_classify(user_message)

    try:
        intent, confidence = classifier.predict_single(user_message)
        logger.debug("Intent classified via BERT: %s (%.2f)", intent, confidence)
        return intent
    except Exception as exc:  # pragma: no cover - 방어적 처리
        logger.error("IntentClassifier inference failed: %s", exc, exc_info=True)
        return _keyword_based_classify(user_message)


# Tool 인스턴스 생성
intent_classification_tool = classify_intent


@lru_cache(maxsize=1)
def _get_classifier() -> Optional[IntentClassifier]:
    """지연 로딩으로 BERT 분류기를 초기화한다."""
    try:
        logger.info("Loading BERT intent classifier...")
        return IntentClassifier()
    except FileNotFoundError as exc:
        logger.error(
            "BERT intent model not found: %s\n"
            "Expected path: fa06-fin-aicc/models/bert_intent_classifier\n"
            "참고: MODEL_DOWNLOAD.md를 확인하세요.",
            exc,
        )
    except Exception as exc:  # pragma: no cover - 초기화 예외
        logger.error("Failed to initialize IntentClassifier: %s", exc, exc_info=True)
    return None


def _keyword_based_classify(user_message: str) -> str:
    """모델 사용이 불가능할 때 사용하는 키워드 기반 fallback."""
    user_message_lower = user_message.lower()

    if any(keyword in user_message_lower for keyword in ["대출", "대출금리", "대출금액", "대출한도"]):
        if any(keyword in user_message_lower for keyword in ["상환", "갚", "반환", "변제"]):
            return "대출 상환"
        return "대출"

    if any(keyword in user_message_lower for keyword in ["예금", "예금금리", "예금이자", "정기예금", "적금"]):
        return "예금"

    if any(keyword in user_message_lower for keyword in ["카드", "신용카드", "체크카드"]):
        return "카드 상품 문의"

    if any(keyword in user_message_lower for keyword in ["상담", "상담사", "상담원", "직원"]):
        return "상담"

    return "일반 문의"
