# ai_engine/graph/nodes/rag_search.py

"""RAG 검색 노드: 벡터 DB 검색 (retriever.py 호출)."""

from __future__ import annotations

from ai_engine.graph.state import GraphState


def rag_search_node(state: GraphState, *, top_k: int = 5) -> GraphState:
    """retriever를 호출해 유사 문서를 찾고 상태(GraphState)에 저장한다.

    TODO:
        - 벡터 DB 검색 구현
        - RAG 검색 실패 시 예외 처리 및 fallback 전략 설정
        - best score(최고 유사도 점수) 계산 후 low confidence(낮은 신뢰도) 플래그 설정
    """
    # TODO: 벡터 DB 검색 구현
    # 임시로 상태만 반환
    return state