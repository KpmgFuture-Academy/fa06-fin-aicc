# ai_engine/graph/nodes/intent_classification.py

from ai_engine.graph.state import GraphState
"""KoBERT 의도 분류 노드"""

def intent_classification_node(state: GraphState) -> GraphState:
    """KoBERT 모델을 호출해 고객 의도를 분류하고 상태에 기록한다."""
    # TODO: KoBERT 모델 호출 구현
    # 임시로 상태만 반환
    return state