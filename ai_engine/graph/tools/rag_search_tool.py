"""RAG 검색 Tool: 벡터 DB에서 유사 문서를 검색합니다."""

from __future__ import annotations

from typing import List, Dict, Any
from langchain.tools import tool
from ai_engine.graph.state import RetrievedDocument


@tool
def search_rag_documents(query: str, top_k: int = 5) -> str:
    """벡터 DB에서 사용자 쿼리와 유사한 문서를 검색합니다.
    
    Args:
        query: 검색할 사용자 메시지 또는 쿼리
        top_k: 반환할 최대 문서 수 (기본값: 5)
        
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
    # TODO: 벡터 DB 검색 구현
    # TODO: retriever를 호출하여 실제 검색 수행
    # TODO: RAG 검색 실패 시 예외 처리 및 fallback 전략 설정
    # TODO: best score 계산 후 low confidence 플래그 설정
    
    # 임시로 빈 결과 반환 (JSON 형식)
    return "[]"


def parse_rag_result(result_json: str) -> List[RetrievedDocument]:
    """RAG 검색 결과 JSON 문자열을 RetrievedDocument 리스트로 파싱합니다.
    
    Args:
        result_json: search_rag_documents가 반환한 JSON 문자열
        
    Returns:
        RetrievedDocument 리스트
    """
    import json
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
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


# Tool 인스턴스 생성
rag_search_tool = search_rag_documents

