"""LangGraph 워크플로우 정의."""

from __future__ import annotations

from typing import Any

try:
    from langgraph.graph import END, StateGraph  # type: ignore[import]
except ImportError:  # pragma: no cover - 개발 환경에서만
    END = None
    StateGraph = None

from ai_engine.graph.nodes.decision_maker import decision_maker_node
from ai_engine.graph.nodes.intent_classification import intent_classification_node
from ai_engine.graph.nodes.llm_answer import llm_answer_node
from ai_engine.graph.nodes.rag_search import rag_search_node
from ai_engine.graph.state import GraphState


def _route_after_intent(state: GraphState) -> str:
    """의도 분류 이후 분기.

    HUMAN_REQ라면 바로 decision_maker로 가고,
    나머지는 RAG → LLM 경로를 타도록 지정한다.
    """
    intent = state.get("intent")
    if intent is not None and intent.name == "HUMAN_REQ":
        return "decision_maker"
    return "rag_search"


def build_workflow() -> Any:
    """LangGraph 워크플로우를 생성해 컴파일 결과를 반환한다."""
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph 패키지가 설치되지 않았습니다. "
            "`pip install langgraph` 이후 다시 시도하세요."
        )

    graph = StateGraph(GraphState)

    graph.add_node("intent_classification", intent_classification_node)
    graph.add_node("rag_search", rag_search_node)
    graph.add_node("llm_answer", llm_answer_node)
    graph.add_node("decision_maker", decision_maker_node)

    graph.set_entry_point("intent_classification")

    graph.add_conditional_edges(
        "intent_classification",
        _route_after_intent,
        {
            "decision_maker": "decision_maker",
            "rag_search": "rag_search",
        },
    )

    graph.add_edge("rag_search", "llm_answer")
    graph.add_edge("llm_answer", "decision_maker")
    graph.add_edge("decision_maker", END)

    return graph.compile()

