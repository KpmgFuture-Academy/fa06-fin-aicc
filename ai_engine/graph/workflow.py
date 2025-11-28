"""LangGraph 워크플로우 정의.

플로우차트 기반 구조:

[HUMAN_REQUIRED = FALSE 플로우 (일반 대화)]
1. 고객 채팅 Input → triage_agent
   (triage_agent 내부에서 intent_classification_tool과 rag_search_tool 사용)
2. triage_agent 분기 (triage_decision 기반):
   - SIMPLE_ANSWER → answer_agent (간단한 답변 생성) → chat_db_storage → END
   - AUTO_ANSWER → answer_agent (RAG 기반 답변 생성) → chat_db_storage → END
   - NEED_MORE_INFO → answer_agent (질문 생성) → chat_db_storage → END
   - HUMAN_REQUIRED → answer_agent (상담사 연결 안내) → chat_db_storage → END
     → is_human_required_flow=True 설정

[HUMAN_REQUIRED = TRUE 플로우 (상담사 연결)]
1. consent_check_node에서 고객 동의 확인 (룰 베이스)
   - "네" 패턴 → customer_consent_received=True → waiting_agent
   - 그 외 전부 → is_human_required_flow=False → triage_agent
2. waiting_agent에서 정보 수집 (대화 히스토리 기반)
   - collected_info 업데이트
   - 부족한 정보만 질문
3. 정보 수집 완료 (info_collection_complete=True)
   → summary_agent → human_transfer → END

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

from ai_engine.graph.nodes.triage_agent import triage_agent_node
from ai_engine.graph.nodes.answer_agent import answer_agent_node
from ai_engine.graph.nodes.chat_db_storage import chat_db_storage_node
from ai_engine.graph.nodes.summary_agent import summary_agent_node
from ai_engine.graph.nodes.human_transfer import consultant_transfer_node
from ai_engine.graph.nodes.waiting_agent import waiting_agent_node
from ai_engine.graph.nodes.consent_check_node import consent_check_node
from ai_engine.graph.state import GraphState
from app.schemas.common import TriageDecisionType


def _entry_router(state: GraphState) -> str:
    """워크플로우 진입점 라우터.
    
    is_human_required_flow와 customer_consent_received 플래그에 따라 분기:
    - is_human_required_flow=TRUE AND customer_consent_received=TRUE → waiting_agent
    - is_human_required_flow=TRUE AND customer_consent_received=FALSE → consent_check
    - 그 외 → triage_agent
    """
    is_human_required_flow = state.get("is_human_required_flow", False)
    customer_consent_received = state.get("customer_consent_received", False)
    
    if is_human_required_flow:
        if customer_consent_received:
            return "waiting_agent"  # 이미 동의함 → 정보 수집
        else:
            return "consent_check"  # 동의 확인 필요
    
    return "triage_agent"


def _route_after_consent(state: GraphState) -> str:
    """consent_check_node 이후 분기.
    
    - customer_consent_received=TRUE → waiting_agent (정보 수집)
    - is_human_required_flow=FALSE → triage_agent (플로우 종료)
    """
    customer_consent_received = state.get("customer_consent_received", False)
    is_human_required_flow = state.get("is_human_required_flow", True)
    
    if customer_consent_received:
        return "waiting_agent"
    
    # 동의하지 않음 (is_human_required_flow=FALSE로 설정됨)
    return "triage_agent"


def _route_after_waiting(state: GraphState) -> str:
    """waiting_agent 이후 분기.
    
    - 정보 수집 완료 시 → summary_agent
    - 정보 수집 중 → chat_db_storage
    """
    info_collection_complete = state.get("info_collection_complete", False)
    
    # 정보 수집 완료 시 summary_agent로 이동
    if info_collection_complete:
        return "summary_agent"
    
    # 정보 수집 중이면 chat_db_storage로 이동 (다음 턴 대기)
    return "chat_db_storage"


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
    graph.add_node("triage_agent", triage_agent_node)
    graph.add_node("answer_agent", answer_agent_node)
    graph.add_node("consent_check", consent_check_node)
    graph.add_node("waiting_agent", waiting_agent_node)
    graph.add_node("chat_db_storage", chat_db_storage_node)
    graph.add_node("summary_agent", summary_agent_node)
    graph.add_node("human_transfer", consultant_transfer_node)

    # 진입점: 조건부 라우터
    graph.set_conditional_entry_point(
        _entry_router,
        {
            "triage_agent": "triage_agent",
            "consent_check": "consent_check",
            "waiting_agent": "waiting_agent",
        },
    )

    # triage_agent 이후 → answer_agent
    graph.add_edge("triage_agent", "answer_agent")

    # answer_agent 이후 → chat_db_storage (일반 플로우)
    graph.add_edge("answer_agent", "chat_db_storage")

    # consent_check 이후 조건부 분기
    graph.add_conditional_edges(
        "consent_check",
        _route_after_consent,
        {
            "waiting_agent": "waiting_agent",  # 동의함
            "triage_agent": "triage_agent",    # 동의하지 않음
        },
    )

    # waiting_agent 이후 조건부 분기
    graph.add_conditional_edges(
        "waiting_agent",
        _route_after_waiting,
        {
            "summary_agent": "summary_agent",      # 정보 수집 완료 시
            "chat_db_storage": "chat_db_storage",  # 정보 수집 중
        },
    )
    
    # summary_agent 이후 → human_transfer
    graph.add_edge("summary_agent", "human_transfer")
    
    # human_transfer 이후 → END
    graph.add_edge("human_transfer", END)
    
    # chat_db_storage 이후 → END
    graph.add_edge("chat_db_storage", END)

    return graph.compile()
