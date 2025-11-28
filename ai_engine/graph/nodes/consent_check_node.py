# ai_engine/graph/nodes/consent_check_node.py

"""HUMAN_REQUIRED 플로우에서 고객 동의를 확인하는 노드.

룰 베이스로 고객의 동의 여부를 확인합니다.
- "네" 패턴 → customer_consent_received=TRUE → waiting_agent로 이동
- 그 외 전부 → is_human_required_flow=FALSE → triage_agent로 이동
"""

from __future__ import annotations
import logging
from ai_engine.graph.state import GraphState

logger = logging.getLogger(__name__)

# 동의 패턴 정의 (룰 베이스)
POSITIVE_PATTERNS = ["네", "넵", "예", "응", "응응", "좋아", "알겠", "연결", "부탁", "그래", "그럼", "ok", "yes", "ㅇㅇ", "ㅇ"]


def consent_check_node(state: GraphState) -> GraphState:
    """고객 동의를 확인하는 노드 (룰 베이스).
    
    - "네" 패턴 → customer_consent_received=TRUE (다음에 waiting_agent로)
    - 그 외 전부 → is_human_required_flow=FALSE (다음에 triage_agent로)
    """
    user_message = state.get("user_message", "").strip().lower()
    session_id = state.get("session_id", "unknown")
    
    # "네" 패턴 확인
    is_consent = any(p in user_message for p in POSITIVE_PATTERNS)
    
    if is_consent:
        # 동의함 → waiting_agent로 이동
        state["customer_consent_received"] = True
        logger.info(f"고객 동의 확인 - 세션: {session_id}, 동의함 → waiting_agent로 이동")
    else:
        # 그 외 전부 → triage_agent로 이동
        state["is_human_required_flow"] = False
        logger.info(f"고객 동의 거부/불명확 - 세션: {session_id}, HUMAN_REQUIRED 플로우 종료 → triage_agent로 이동")
    
    return state

