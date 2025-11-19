"""의도 분류 Tool: KoBERT 모델을 호출하여 고객 메시지의 문맥 의도를 분류합니다."""

from __future__ import annotations

from typing import Annotated
from langchain.tools import tool


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
    # TODO: KoBERT 모델 호출 구현
    # 임시로 키워드 기반 기본 분류
    user_message_lower = user_message.lower()
    
    # 대출 관련
    if any(keyword in user_message_lower for keyword in ["대출", "대출금리", "대출금액", "대출한도"]):
        if any(keyword in user_message_lower for keyword in ["상환", "갚", "반환", "변제"]):
            return "대출 상환"
        return "대출"
    
    # 예금 관련
    if any(keyword in user_message_lower for keyword in ["예금", "예금금리", "예금이자", "정기예금", "적금"]):
        return "예금"
    
    # 카드 관련
    if any(keyword in user_message_lower for keyword in ["카드", "신용카드", "체크카드"]):
        return "카드 상품 문의"
    
    # 상담 관련
    if any(keyword in user_message_lower for keyword in ["상담", "상담사", "상담원", "직원"]):
        return "상담"
    
    # 기본값: 일반 문의
    return "일반 문의"


# Tool 인스턴스 생성
intent_classification_tool = classify_intent
