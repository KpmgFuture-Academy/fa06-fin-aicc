"""LangGraph 워크플로우 정의.

플로우차트 기반 구조:
1. 고객 채팅 Input → intent_classification
2. intent_classification → decision_agent
3. decision_agent 분기:
   - 상담사 연결 필요 → summary_agent → human_transfer → END
   - 챗봇으로 처리 가능 → rag_search → answer_agent → chat_db_storage → END
   
한 사용자(세션)에 대해 여러 턴의 대화가 가능하며, 상담사 이관이 결정된 시점에만
전체 대화를 요약하여 대시보드에 표시합니다.
"""

from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, StateGraph  # type: ignore[import]
except ImportError:  # pragma: no cover - 개발 환경에서만
    END = None
    StateGraph = None

from ai_engine.graph.nodes.decision_agent import decision_agent_node
from ai_engine.graph.nodes.intent_classification import intent_classification_node
from ai_engine.graph.nodes.answer_agent import answer_agent_node
from ai_engine.graph.nodes.rag_search import rag_search_node
from ai_engine.graph.nodes.chat_db_storage import chat_db_storage_node
from ai_engine.graph.nodes.summary_agent import summary_agent_node
from ai_engine.graph.nodes.human_transfer import consultant_transfer_node
from ai_engine.graph.state import GraphState


def _route_after_decision(state: GraphState) -> str:
    """판단 에이전트 이후 분기.

    requires_consultant가 True면 summary_agent로 (요약 생성 후 상담사 연결),
    False면 rag_search 경로로 이동.
    """
    requires_consultant = state.get("requires_consultant", False)
    if requires_consultant:
        return "summary_agent"
    return "rag_search"


def build_workflow() -> Any:
    """LangGraph 워크플로우를 생성해 컴파일 결과를 반환한다.

    실행 후 graph.get_graph().draw_mermaid() 또는
    graph.get_graph().print_ascii()로 구조를 시각화할 수 있습니다.
    """
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph 패키지가 설치되지 않았습니다. "
            "`pip install langgraph` 이후 다시 시도하세요."
        )

    graph = StateGraph(GraphState)

    # 모든 노드 등록
    graph.add_node("intent_classification", intent_classification_node)
    graph.add_node("decision_agent", decision_agent_node)
    graph.add_node("rag_search", rag_search_node)
    graph.add_node("answer_agent", answer_agent_node)
    graph.add_node("chat_db_storage", chat_db_storage_node)
    graph.add_node("summary_agent", summary_agent_node)
    graph.add_node("human_transfer", consultant_transfer_node)

    # 진입점 설정
    graph.set_entry_point("intent_classification")

    # 엣지 연결
    graph.add_edge("intent_classification", "decision_agent")

    # decision_agent 이후 조건부 분기
    graph.add_conditional_edges(
        "decision_agent",
        _route_after_decision,
        {
            "summary_agent": "summary_agent",
            "rag_search": "rag_search",
        },
    )

    # 챗봇 처리 경로
    graph.add_edge("rag_search", "answer_agent")
    graph.add_edge("answer_agent", "chat_db_storage")
    graph.add_edge("chat_db_storage", END)  # 챗봇 처리 후 종료 (다음 턴 대기)

    # 상담사 이관 경로: 요약 생성 후 상담사 연결
    graph.add_edge("summary_agent", "human_transfer")
    graph.add_edge("human_transfer", END)  # 상담사 연결 완료 후 종료

    return graph.compile()