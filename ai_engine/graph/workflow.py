"""LangGraph 워크플로우 정의.

플로우차트 기반 구조:
1. 고객 채팅 Input → triage_agent
   (triage_agent 내부에서 intent_classification_tool과 rag_search_tool을 사용)
2. triage_agent 분기 (triage_decision 기반):
   - SIMPLE_ANSWER → answer_agent (간단한 답변 생성) → chat_db_storage → END
   - AUTO_ANSWER → answer_agent (RAG 기반 답변 생성) → chat_db_storage → END
   - NEED_MORE_INFO → answer_agent (질문 생성) → chat_db_storage → END
   - HUMAN_REQUIRED → answer_agent (상담사 연결 안내) → chat_db_storage → END

정보 수집 단계:
- HUMAN_REQUIRED + 긍정 응답 → is_collecting_info=True 설정
- 정보 수집 중 (is_collecting_info=True):
  - triage_agent에서 Tool 사용 건너뛰고 NEED_MORE_INFO 반환
  - answer_agent에서 정보 수집 질문 생성 (info_collection_count 증가)
  - 10회 도달 시: answer_agent → summary_agent → human_transfer → chat_db_storage → END

한 사용자(세션)에 대해 여러 턴의 대화가 가능하며, 상담사 이관이 결정된 시점에만
전체 대화를 요약하여 대시보드에 표시합니다.

주의: intent_classification과 rag_search는 이제 tool로 전환되어
triage_agent_node와 answer_agent_node에서 직접 사용됩니다.
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
from ai_engine.graph.state import GraphState
from app.schemas.common import TriageDecisionType


def _route_after_triage(state: GraphState) -> str:
    """Triage 에이전트 이후 분기.

    triage_decision 값에 따라 분기:
    - SIMPLE_ANSWER: answer_agent (간단한 답변 생성)
    - AUTO_ANSWER: answer_agent (RAG 기반 답변 생성)
    - NEED_MORE_INFO: answer_agent (질문 생성)
    - HUMAN_REQUIRED: answer_agent (상담사 연결 안내)
    
    모든 케이스가 answer_agent를 거치며, answer_agent 내부에서 triage_decision에 따라
    다른 방식으로 처리합니다.
    """
    triage_decision = state.get("triage_decision")
    
    # triage_decision이 없거나 예상치 못한 값인 경우 answer_agent로 (fallback)
    if triage_decision not in [TriageDecisionType.SIMPLE_ANSWER,
                                TriageDecisionType.AUTO_ANSWER,
                                TriageDecisionType.NEED_MORE_INFO, 
                                TriageDecisionType.HUMAN_REQUIRED]:
        return "answer_agent"
    
    # 모든 케이스가 answer_agent로 이동
    return "answer_agent"


def _route_after_answer(state: GraphState) -> str:
    """answer_agent 이후 분기.
    
    정보 수집 10번째 턴 도달 시 summary_agent로 이동,
    그 외에는 chat_db_storage로 이동.
    """
    info_collection_count = state.get("info_collection_count", 0)
    
    # 10번째 턴 도달 시 summary_agent로 이동
    if info_collection_count >= 10:
        return "summary_agent"  # 정보 수집 완료 → 요약
    return "chat_db_storage"  # 일반 케이스 (1~9번째 질문 또는 일반 대화)


def build_workflow() -> Any:
    """LangGraph 워크플로우를 생성해 컴파일 결과를 반환한다.

    실행 후 graph.get_graph().draw_mermaid() 또는
    graph.get_graph().print_ascii()로 구조를 시각화할 수 있습니다.
    
    참고: intent_classification과 rag_search는 tool로 전환되어
    triage_agent_node와 answer_agent_node 내부에서 사용됩니다.
    """
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph 패키지가 설치되지 않았습니다. "
            "`pip install langgraph` 이후 다시 시도하세요."
        )

    graph = StateGraph(GraphState)

    # 모든 노드 등록 (intent_classification과 rag_search는 tool로 전환됨)
    graph.add_node("triage_agent", triage_agent_node)
    graph.add_node("answer_agent", answer_agent_node)
    graph.add_node("chat_db_storage", chat_db_storage_node)
    graph.add_node("summary_agent", summary_agent_node)
    graph.add_node("human_transfer", consultant_transfer_node)

    # 진입점 설정 (triage_agent가 intent_classification_tool과 rag_search_tool을 내부적으로 사용)
    graph.set_entry_point("triage_agent")

    # triage_agent 이후 조건부 분기
    # 모든 케이스가 answer_agent로 이동 (answer_agent 내부에서 triage_decision에 따라 처리)
    graph.add_conditional_edges(
        "triage_agent",
        _route_after_triage,
        {
            "answer_agent": "answer_agent",
        },
    )

    # answer_agent 이후 조건부 분기
    # 정보 수집 10회 완료 시 summary_agent로, 그 외에는 chat_db_storage로 이동
    graph.add_conditional_edges(
        "answer_agent",
        _route_after_answer,
        {
            "summary_agent": "summary_agent",
            "chat_db_storage": "chat_db_storage",
        },
    )
    
    # summary_agent 이후 human_transfer로 이동
    graph.add_edge("summary_agent", "human_transfer")
    
    # human_transfer 이후 chat_db_storage로 이동
    graph.add_edge("human_transfer", "chat_db_storage")
    
    # chat_db_storage 이후 END
    graph.add_edge("chat_db_storage", END)  # 처리 후 종료 (다음 턴 대기)

    return graph.compile()