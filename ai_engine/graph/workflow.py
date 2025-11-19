"""LangGraph 워크플로우 정의.

플로우차트 기반 구조:
1. 고객 채팅 Input → decision_agent
   (decision_agent 내부에서 intent_classification_tool과 rag_search_tool을 사용)
2. decision_agent 분기:
   - 상담사 연결 필요 → summary_agent → human_transfer → END
   - 챗봇으로 처리 가능 → answer_agent → chat_db_storage → END
     (answer_agent 내부에서 rag_search_tool을 사용)
   
한 사용자(세션)에 대해 여러 턴의 대화가 가능하며, 상담사 이관이 결정된 시점에만
전체 대화를 요약하여 대시보드에 표시합니다.

주의: intent_classification과 rag_search는 이제 tool로 전환되어
decision_agent_node와 answer_agent_node에서 직접 사용됩니다.
"""

from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, StateGraph  # type: ignore[import]
except ImportError:  # pragma: no cover - 개발 환경에서만
    END = None
    StateGraph = None

from ai_engine.graph.nodes.decision_agent import decision_agent_node
from ai_engine.graph.nodes.answer_agent import answer_agent_node
from ai_engine.graph.nodes.chat_db_storage import chat_db_storage_node
from ai_engine.graph.nodes.summary_agent import summary_agent_node
from ai_engine.graph.nodes.human_transfer import consultant_transfer_node
from ai_engine.graph.state import GraphState


def _route_after_decision(state: GraphState) -> str:
    """판단 에이전트 이후 분기.

    requires_consultant가 True면 summary_agent로 (요약 생성 후 상담사 연결),
    False면 answer_agent 경로로 이동 (answer_agent가 내부적으로 rag_search_tool 사용).
    """
    requires_consultant = state.get("requires_consultant", False)
    if requires_consultant:
        return "summary_agent"
    return "answer_agent"


def build_workflow() -> Any:
    """LangGraph 워크플로우를 생성해 컴파일 결과를 반환한다.

    실행 후 graph.get_graph().draw_mermaid() 또는
    graph.get_graph().print_ascii()로 구조를 시각화할 수 있습니다.
    
    참고: intent_classification과 rag_search는 tool로 전환되어
    decision_agent_node와 answer_agent_node 내부에서 사용됩니다.
    """
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph 패키지가 설치되지 않았습니다. "
            "`pip install langgraph` 이후 다시 시도하세요."
        )

    graph = StateGraph(GraphState)

    # 모든 노드 등록 (intent_classification과 rag_search는 tool로 전환됨)
    graph.add_node("decision_agent", decision_agent_node)
    graph.add_node("answer_agent", answer_agent_node)
    graph.add_node("chat_db_storage", chat_db_storage_node)
    graph.add_node("summary_agent", summary_agent_node)
    graph.add_node("human_transfer", consultant_transfer_node)

    # 진입점 설정 (decision_agent가 intent_classification_tool과 rag_search_tool을 내부적으로 사용)
    graph.set_entry_point("decision_agent")

    # decision_agent 이후 조건부 분기
    graph.add_conditional_edges(
        "decision_agent",
        _route_after_decision,
        {
            "summary_agent": "summary_agent",
            "answer_agent": "answer_agent",
        },
    )

    # 챗봇 처리 경로 (answer_agent가 내부적으로 rag_search_tool 사용)
    graph.add_edge("answer_agent", "chat_db_storage")
    graph.add_edge("chat_db_storage", END)  # 챗봇 처리 후 종료 (다음 턴 대기)

    # 상담사 이관 경로: 요약 생성 후 상담사 연결, DB 저장 후 종료
    graph.add_edge("summary_agent", "human_transfer")
    graph.add_edge("human_transfer", "chat_db_storage")  # 상담사 연결 경로에서도 DB 저장
    graph.add_edge("chat_db_storage", END)  # 상담사 연결 완료 후 종료

    return graph.compile()