# ai_engine/graph/nodes/decision_maker.py

"""상담원 이관 판단 노드."""

from __future__ import annotations

from typing import List

from ai_engine.graph.state import GraphState
from app.schemas.common import ActionType, IntentType


HANDOVER_REASON_FORCE_INTENT = "INTENT_REQUIRES_HUMAN"
HANDOVER_REASON_USER_REQUEST = "USER_REQUEST"
HANDOVER_REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
HANDOVER_REASON_SYSTEM_ERROR = "SYSTEM_ERROR"


def decision_maker_node(state: GraphState) -> GraphState:
    """의도/유사도/사용자 요청 플래그를 종합해 상담원 이관 여부를 결정한다."""

    # GraphState는 TypedDict로 정의되어 있지만 실제 실행 시 dict로 다뤄진다.
    metadata = state.get("metadata") or {}
    state["metadata"] = metadata

    reasons: List[str] = metadata.get("handover_reasons", [])

    intent = state.get("intent")

    force_handover = metadata.get("force_handover", False)
    rag_low_confidence = metadata.get("rag_low_confidence", False)
    user_requested_handover = metadata.get("user_requested_handover", False)
    llm_error = metadata.get("llm_error", False) or metadata.get("rag_error", False)

    if intent == IntentType.HUMAN_REQ:
        force_handover = True

    if force_handover and HANDOVER_REASON_FORCE_INTENT not in reasons:
        reasons.append(HANDOVER_REASON_FORCE_INTENT)
    if user_requested_handover and HANDOVER_REASON_USER_REQUEST not in reasons:
        reasons.append(HANDOVER_REASON_USER_REQUEST)
    if rag_low_confidence and HANDOVER_REASON_LOW_CONFIDENCE not in reasons:
        reasons.append(HANDOVER_REASON_LOW_CONFIDENCE)
    if llm_error and HANDOVER_REASON_SYSTEM_ERROR not in reasons:
        reasons.append(HANDOVER_REASON_SYSTEM_ERROR)

    metadata["handover_reasons"] = reasons

    should_handover = any(
        (
            force_handover,
            user_requested_handover,
            rag_low_confidence,
            llm_error,
        )
    )

    state["suggested_action"] = (
        ActionType.HANDOVER if should_handover else ActionType.CONTINUE
    )

    return state

