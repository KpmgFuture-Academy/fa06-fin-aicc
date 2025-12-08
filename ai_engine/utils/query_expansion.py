"""쿼리 확장 유틸리티: 검색 쿼리를 개선하여 유사도를 높입니다."""

from __future__ import annotations
from typing import List


# 금융 용어 동의어 및 관련어 사전
FINANCIAL_SYNONYMS = {
    "카드론": ["카드론", "장기카드대출", "카드 대출", "신용카드 대출", "카드론 한도", "카드론 금리"],
    "현금서비스": ["현금서비스", "현금 서비스", "Cash Advance", "현금 인출", "카드 현금서비스"],
    "한도": ["한도", "이용한도", "신용한도", "대출한도", "한도 조회", "한도 확인"],
    "금리": ["금리", "이자율", "이자", "금리율", "대출금리", "이자율"],
    "대출": ["대출", "융자", "차입", "대출금", "대출 상품"],
    "예금": ["예금", "적금", "저축", "예적금", "예금 상품"],
    "신용카드": ["신용카드", "카드", "신용 카드", "체크카드", "카드 상품"],
    "결제일": ["결제일", "결제 일자", "청구일", "납부일", "결제 날짜"],
}


def expand_query(query: str) -> str:
    """검색 쿼리를 확장하여 관련 키워드를 추가합니다.
    
    Args:
        query: 원본 검색 쿼리
        
    Returns:
        확장된 검색 쿼리 (원본 + 관련 키워드)
    """
    expanded_terms = [query]  # 원본 쿼리 포함
    
    # 쿼리에서 키워드 찾기 및 동의어 추가
    query_lower = query.lower()
    
    for keyword, synonyms in FINANCIAL_SYNONYMS.items():
        if keyword in query_lower:
            # 관련 동의어 중 일부 추가 (너무 많이 추가하면 노이즈 증가)
            for synonym in synonyms[:2]:  # 상위 2개만 추가
                if synonym not in query_lower and synonym not in expanded_terms:
                    expanded_terms.append(synonym)
    
    # 확장된 쿼리 조합 (원본 + 관련 키워드)
    expanded_query = " ".join(expanded_terms)
    
    return expanded_query


def extract_keywords(query: str) -> List[str]:
    """쿼리에서 핵심 키워드를 추출합니다.
    
    Args:
        query: 검색 쿼리
        
    Returns:
        추출된 키워드 리스트
    """
    keywords = []
    query_lower = query.lower()
    
    for keyword in FINANCIAL_SYNONYMS.keys():
        if keyword in query_lower:
            keywords.append(keyword)
    
    return keywords

