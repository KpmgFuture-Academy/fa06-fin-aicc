# ai_engine/graph/nodes/llm_answer.py

"""LLM 답변 노드: GPT 계열 모델 호출."""

from __future__ import annotations

from ai_engine.graph.state import GraphState


def llm_answer_node(state: GraphState) -> GraphState:
    """프롬프트를 구성해 LLM에게 답변 생성을 요청하고 상태를 갱신한다."""

    # 1) 상담원 이관 관련 플래그 읽기 (앞선 노드에서 세팅)
    # force_handover_intent = state.metadata.get("force_handover", False)
    # rag_low_confidence = state.metadata.get("rag_low_confidence", False)
    # user_requested_handover = state.metadata.get("user_requested_handover", False)

    # 2) 프롬프트 생성 (상담원 신호를 함께 전달)
    # prompt = build_rag_prompt(
    #     user_message=state["user_message"],
    #     documents=state.get("retrieved_documents", []),
    #     intent=state.get("intent"),
    #     force_handover_intent=force_handover_intent,
    #     rag_low_confidence=rag_low_confidence,
    #     user_requested_handover=user_requested_handover,
    # )

    # 3) LLM 호출 (예: GPT-4o, LangGraph service)
    # llm_response = llm_client.generate(prompt)

    # 4) 상태 갱신
    # state["ai_message"] = llm_response.text
    # state["source_documents"] = state.get("source_documents", [])

    # 5) 예외 / 실패 시 fallback
    # try:
    #     ...
    # except Exception as exc:
    #     state["ai_message"] = "죄송합니다. 잠시 후 다시 시도해주세요."
    #     state["metadata"]["llm_error"] = str(exc)

    raise NotImplementedError("llm_answer_node() is not implemented yet.")