# ai_engine/graph/nodes/intent_classification.py
# KoBERT 의도 분류 노드

from ai_engine.graph.state import GraphState
from ai_engine.tools.intent_classifier import classify_intent

def intent_classification_node(state: GraphState) -> GraphState:
    metadata = state.get("metadata") or {}
    state["metadata"] = metadata

    try:
        result = classify_intent(state["user_message"])
    except Exception as exc:
        metadata["intent_error"] = str(exc)
        metadata["force_handover"] = True
        # 기본값
        state["intent"] = IntentType.HUMAN_REQ
        return state

    state["intent"] = result.intent
    metadata["intent_confidence"] = result.confidence
    metadata["intent_raw_label"] = result.raw_label
    if result.intent == IntentType.HUMAN_REQ:
        metadata["force_handover"] = True

    return state