# ai_engine/graph/nodes/consent_check_node.py

"""HUMAN_REQUIRED 플로우에서 고객 동의를 확인하는 노드.

룰 베이스로 고객의 동의 여부를 확인합니다.
- 명시적 거부 패턴 → is_human_required_flow=FALSE → triage_agent로 이동
- 그 외 전부 (동의 또는 추가 메시지) → customer_consent_received=TRUE → waiting_agent로 이동

이 로직은 빠른 연속 메시지("빨리 도와주세요", "급해요" 등)가
거부로 처리되는 문제를 방지합니다.
"""

from __future__ import annotations
import logging
from ai_engine.graph.state import GraphState

logger = logging.getLogger(__name__)

# 명시적 거부 패턴 정의 (룰 베이스)
# 이 패턴이 있을 때만 거부로 처리
NEGATIVE_PATTERNS = [
    "아니", "싫", "안 해", "안해", "괜찮아", "됐어", "필요 없", "필요없",
    "상담사 안", "연결 안", "그냥 됐", "취소", "안 할", "안할", "말고",
    "no", "nope", "ㄴㄴ", "ㄴ"
]


def consent_check_node(state: GraphState) -> GraphState:
    """고객 동의를 확인하는 노드 (룰 베이스).

    - 명시적 거부 패턴 → is_human_required_flow=FALSE (다음에 triage_agent로)
    - 그 외 전부 → customer_consent_received=TRUE (다음에 waiting_agent로)

    빠른 연속 메시지("빨리 도와주세요", "급해요" 등)는 동의로 간주합니다.
    """
    user_message = state.get("user_message", "").strip().lower()
    session_id = state.get("session_id", "unknown")

    # 명시적 거부 패턴 확인
    is_rejection = any(p in user_message for p in NEGATIVE_PATTERNS)

    if is_rejection:
        # 명시적 거부 → triage_agent로 이동
        state["is_human_required_flow"] = False

        # 고객이 상담사 연결을 거부했음을 표시
        # triage_agent가 같은 맥락에서 다시 HUMAN_REQUIRED로 판단하지 않도록
        state["customer_declined_handover"] = True

        # AI 응답 메시지 설정 (일반 대화로 전환)
        state["ai_message"] = "알겠습니다. 다른 도움이 필요하시면 말씀해 주세요."

        logger.info(f"고객 명시적 거부 - 세션: {session_id}, HUMAN_REQUIRED 플로우 종료 → triage_agent로 이동")
    else:
        # 그 외 전부 (동의 또는 추가 메시지) → waiting_agent로 이동
        state["customer_consent_received"] = True

        # collected_info 빈 포맷 초기화 (DB에 저장될 스키마)
        # 이미 값이 있으면 유지, 없으면 빈 딕셔너리로 초기화
        # (실제 슬롯은 waiting_agent에서 카테고리에 따라 동적으로 결정됨)
        if not state.get("collected_info"):
            state["collected_info"] = {}
            logger.info(f"collected_info 빈 딕셔너리 초기화 - 세션: {session_id}")

        logger.info(f"고객 동의/추가메시지 - 세션: {session_id}, 동의로 처리 → waiting_agent로 이동")

    return state

