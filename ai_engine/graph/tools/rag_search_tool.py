"""RAG 검색 Tool: 벡터 DB에서 유사 문서를 검색합니다."""

from __future__ import annotations

import json
import logging
from typing import List, Dict, Any
from langchain_core.tools import tool
from ai_engine.graph.state import RetrievedDocument
from ai_engine.vector_store import search_documents

# 로깅 설정
logger = logging.getLogger(__name__)

# 신뢰도 임계값 설정
LOW_CONFIDENCE_THRESHOLD = 0.5  # 이 값보다 낮으면 신뢰도 낮음으로 판단


@tool
def search_rag_documents(query: str, top_k: int = 3) -> str:
    """벡터 DB에서 사용자 쿼리와 유사한 문서를 검색합니다.
    
    Args:
        query: 검색할 사용자 메시지 또는 쿼리
        top_k: 반환할 최대 문서 수 (기본값: 3)
        
    Returns:
        JSON 형태의 검색 결과 문자열. 형식:
        [
            {
                "content": "문서 내용",
                "source": "출처 파일명",
                "page": 1,
                "score": 0.95
            },
            ...
        ]
        
    Examples:
        search_rag_documents("대출 금리") -> "[{\"content\": \"...\", \"source\": \"상품설명서.pdf\", ...}]"
    """
    try:
        # 벡터 DB에서 문서 검색
        results = search_documents(
            query=query,
            top_k=top_k,
            score_threshold=0.3  # 최소 점수 임계값 (필요시 조정)
        )
        
        # 검색 결과가 없는 경우
        if not results:
            logger.warning(f"RAG 검색 결과 없음: query='{query}'")
            return "[]"
        
        # JSON 문자열로 변환
        result_json = json.dumps(results, ensure_ascii=False, indent=2)
        
        logger.info(f"RAG 검색 완료: query='{query}', found={len(results)} documents")
        return result_json
        
    except Exception as e:
        # RAG 검색 실패 시 예외 처리 및 fallback
        logger.error(f"RAG 검색 실패: query='{query}', error={str(e)}", exc_info=True)
        
        # 빈 결과 반환 (fallback)
        return "[]"


def parse_rag_result(result_json: str) -> List[RetrievedDocument]:
    """RAG 검색 결과 JSON 문자열을 RetrievedDocument 리스트로 파싱합니다.
    
    Args:
        result_json: search_rag_documents가 반환한 JSON 문자열
        
    Returns:
        RetrievedDocument 리스트
    """
    try:
        data = json.loads(result_json)
        return [
            RetrievedDocument(
                content=doc.get("content", ""),
                source=doc.get("source", "unknown"),
                page=doc.get("page", 0),
                score=doc.get("score", 0.0)
            )
            for doc in data
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"RAG 결과 파싱 실패: {str(e)}", exc_info=True)
        return []


def get_best_score(documents: List[RetrievedDocument]) -> float:
    """검색된 문서들 중 최고 유사도 점수를 반환합니다.
    
    Args:
        documents: RetrievedDocument 리스트
        
    Returns:
        최고 유사도 점수 (문서가 없으면 0.0)
    """
    if not documents:
        return 0.0
    return max(doc["score"] for doc in documents)


def is_low_confidence(documents: List[RetrievedDocument]) -> bool:
    """검색 결과의 신뢰도가 낮은지 판단합니다.
    
    Args:
        documents: RetrievedDocument 리스트
        
    Returns:
        신뢰도가 낮으면 True, 그렇지 않으면 False
    """
    best_score = get_best_score(documents)
    return best_score < LOW_CONFIDENCE_THRESHOLD


# Tool 인스턴스 생성
rag_search_tool = search_rag_documents

