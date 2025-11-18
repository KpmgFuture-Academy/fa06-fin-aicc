"""LangGraph 워크플로우 정의.

플로우차트 기반 구조:
1. 고객 채팅 Input → intent_classification
2. intent_classification → decision_agent
3. decision_agent 분기:
   - 상담사 연결 필요 → human_transfer → END
   - 챗봇으로 처리 가능 → rag_search → answer_agent → chat_db_storage
4. chat_db_storage 분기:
   - 이번 턴이 상담 종료가 아님 → 다음 채팅 대기
   - 이번 턴이 상담 종료임 → summary_agent → END (상담원 대시보드)
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

    requires_consultant가 True면 human_transfer로,
    False면 rag_search 경로로 이동.
    """
    requires_consultant = state.get("requires_consultant", False)
    if requires_consultant:
        return "human_transfer"
    return "rag_search"


def _route_after_storage(state: GraphState) -> str:
    """DB 저장 이후 분기.

    is_session_end가 True면 summary_agent로,
    False면 여기서 턴 종료(END).
    """
    is_session_end = state.get("is_session_end", False)
    if is_session_end:
        return "end_session"
    return "continue_chat"


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
            "human_transfer": "human_transfer",
            "rag_search": "rag_search",
        },
    )

    # 챗봇 처리 경로
    graph.add_edge("rag_search", "answer_agent")
    graph.add_edge("answer_agent", "chat_db_storage")

    # chat_db_storage 이후: 이번 턴이 마지막인지에 따라 분기
    graph.add_conditional_edges(
        "chat_db_storage",
        _route_after_storage,
        {
            "continue_chat": END,          # 상담 계속: 여기서 턴 종료
            "end_session": "summary_agent" # 상담 종료: 요약/대시보드로
        },
    )

    # summary_agent 이후 종료
    graph.add_edge("summary_agent", END)

    # 상담사 이관 경로 종료
    graph.add_edge("human_transfer", END)

    return graph.compile()