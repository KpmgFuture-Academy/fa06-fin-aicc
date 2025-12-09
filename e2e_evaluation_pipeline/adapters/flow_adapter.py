# e2e_evaluation_pipeline/adapters/flow_adapter.py
"""Flow 평가를 위한 LangGraph 노드 흐름 어댑터.

워크플로우 실행 시 노드 시퀀스를 추적하고
예상 흐름과 비교하여 평가합니다.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FlowType(Enum):
    """플로우 타입"""
    SIMPLE_ANSWER = "SIMPLE_ANSWER"
    AUTO_ANSWER = "AUTO_ANSWER"
    NEED_MORE_INFO = "NEED_MORE_INFO"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


@dataclass
class FlowExecutionResult:
    """플로우 실행 결과"""
    flow_type: str
    node_sequence: List[str]
    expected_sequence: List[str]
    is_correct_flow: bool
    missing_nodes: List[str] = field(default_factory=list)
    extra_nodes: List[str] = field(default_factory=list)
    error: Optional[str] = None


# 예상 노드 시퀀스 정의
EXPECTED_FLOWS = {
    # 일반 플로우 (HUMAN_REQUIRED = FALSE)
    "SIMPLE_ANSWER": [
        "triage_agent",
        "answer_agent",
        "chat_db_storage"
    ],
    "AUTO_ANSWER": [
        "triage_agent",
        "answer_agent",
        "chat_db_storage"
    ],
    "NEED_MORE_INFO": [
        "triage_agent",
        "answer_agent",
        "chat_db_storage"
    ],

    # 상담사 연결 플로우 (HUMAN_REQUIRED = TRUE)
    # 1단계: 상담사 연결 안내
    "HUMAN_REQUIRED_INITIAL": [
        "triage_agent",
        "answer_agent",
        "chat_db_storage"
    ],
    # 2단계: 동의 확인
    "HUMAN_REQUIRED_CONSENT_CHECK": [
        "consent_check"
    ],
    # 3단계: 정보 수집 (동의 후)
    "HUMAN_REQUIRED_INFO_COLLECTION": [
        "waiting_agent",
        "chat_db_storage"
    ],
    # 4단계: 정보 수집 완료 후 이관
    "HUMAN_REQUIRED_TRANSFER": [
        "waiting_agent",
        "chat_db_storage",
        "summary_agent",
        "human_transfer"
    ]
}


class FlowAdapter:
    """Flow 평가 어댑터.

    LangGraph 워크플로우의 노드 시퀀스를 추적하고
    예상 흐름과 비교합니다.
    """

    def __init__(self):
        self._langgraph_adapter = None
        self._initialized = False

    def _ensure_initialized(self):
        """LangGraph 어댑터 지연 초기화"""
        if self._initialized:
            return

        try:
            from .langgraph_adapter import LangGraphAdapter
            self._langgraph_adapter = LangGraphAdapter()
            self._initialized = True
            logger.info("Flow 어댑터 초기화 완료")
        except Exception as e:
            logger.error(f"Flow 어댑터 초기화 실패: {e}")
            raise RuntimeError(f"Flow 어댑터 초기화 실패: {e}")

    def get_expected_flow(
        self,
        triage_decision: str,
        is_human_required_flow: bool = False,
        customer_consent_received: bool = False,
        info_collection_complete: bool = False
    ) -> List[str]:
        """상태에 따른 예상 노드 흐름 반환.

        Args:
            triage_decision: triage 결정 (SIMPLE_ANSWER, AUTO_ANSWER, etc.)
            is_human_required_flow: HUMAN_REQUIRED 플로우 여부
            customer_consent_received: 고객 동의 여부
            info_collection_complete: 정보 수집 완료 여부

        Returns:
            예상 노드 시퀀스
        """
        if not is_human_required_flow:
            # 일반 플로우
            return EXPECTED_FLOWS.get(triage_decision, EXPECTED_FLOWS["SIMPLE_ANSWER"])

        # HUMAN_REQUIRED 플로우
        if not customer_consent_received:
            return EXPECTED_FLOWS["HUMAN_REQUIRED_CONSENT_CHECK"]

        if info_collection_complete:
            return EXPECTED_FLOWS["HUMAN_REQUIRED_TRANSFER"]
        else:
            return EXPECTED_FLOWS["HUMAN_REQUIRED_INFO_COLLECTION"]

    def evaluate_flow(
        self,
        actual_sequence: List[str],
        expected_sequence: List[str],
        strict: bool = False
    ) -> Dict[str, Any]:
        """노드 시퀀스 평가.

        Args:
            actual_sequence: 실제 실행된 노드 시퀀스
            expected_sequence: 예상 노드 시퀀스
            strict: 순서까지 정확히 일치해야 하는지 여부

        Returns:
            평가 결과 딕셔너리
        """
        actual_set = set(actual_sequence)
        expected_set = set(expected_sequence)

        missing = expected_set - actual_set
        extra = actual_set - expected_set

        # 순서 일치 확인 (strict 모드)
        order_correct = True
        if strict and not missing and not extra:
            order_correct = actual_sequence == expected_sequence

        # 필수 노드 포함 여부
        required_nodes_present = len(missing) == 0

        # 점수 계산 (0~1)
        if not expected_sequence:
            score = 1.0 if not actual_sequence else 0.0
        else:
            matched = len(expected_set & actual_set)
            score = matched / len(expected_set)

            # 순서 불일치 시 감점
            if not order_correct:
                score *= 0.9

            # 불필요한 노드 있으면 감점
            if extra:
                score *= 0.95

        return {
            "score": score,
            "is_correct": required_nodes_present and (not strict or order_correct),
            "order_correct": order_correct,
            "missing_nodes": list(missing),
            "extra_nodes": list(extra),
            "expected_sequence": expected_sequence,
            "actual_sequence": actual_sequence
        }

    def trace_execution(
        self,
        user_message: str,
        session_id: str = "flow_eval",
        initial_state: Optional[Dict[str, Any]] = None
    ) -> FlowExecutionResult:
        """워크플로우 실행 및 흐름 추적.

        Args:
            user_message: 사용자 메시지
            session_id: 세션 ID
            initial_state: 초기 상태

        Returns:
            FlowExecutionResult: 실행 결과
        """
        self._ensure_initialized()

        try:
            # 워크플로우 실행
            result = self._langgraph_adapter.execute(
                user_message=user_message,
                session_id=session_id,
                initial_state=initial_state
            )

            # 예상 흐름 결정
            triage_decision = result.triage_decision or "SIMPLE_ANSWER"
            is_human_flow = result.is_human_required_flow
            consent = initial_state.get("customer_consent_received", False) if initial_state else False
            info_complete = result.info_collection_complete

            expected = self.get_expected_flow(
                triage_decision=triage_decision,
                is_human_required_flow=is_human_flow,
                customer_consent_received=consent,
                info_collection_complete=info_complete
            )

            # 평가
            evaluation = self.evaluate_flow(
                actual_sequence=result.node_sequence,
                expected_sequence=expected,
                strict=False
            )

            return FlowExecutionResult(
                flow_type=triage_decision,
                node_sequence=result.node_sequence,
                expected_sequence=expected,
                is_correct_flow=evaluation["is_correct"],
                missing_nodes=evaluation["missing_nodes"],
                extra_nodes=evaluation["extra_nodes"]
            )

        except Exception as e:
            logger.error(f"플로우 추적 오류: {e}", exc_info=True)
            return FlowExecutionResult(
                flow_type="ERROR",
                node_sequence=[],
                expected_sequence=[],
                is_correct_flow=False,
                error=str(e)
            )

    def trace_multi_turn(
        self,
        messages: List[str],
        session_id: str = "flow_eval"
    ) -> List[FlowExecutionResult]:
        """멀티턴 대화 흐름 추적.

        Args:
            messages: 사용자 메시지 리스트
            session_id: 세션 ID

        Returns:
            각 턴별 FlowExecutionResult 리스트
        """
        self._ensure_initialized()

        results = []
        current_state = None

        for i, message in enumerate(messages):
            logger.info(f"플로우 추적 턴 {i+1}/{len(messages)}")

            result = self.trace_execution(
                user_message=message,
                session_id=session_id,
                initial_state=current_state
            )
            results.append(result)

            # 다음 턴을 위한 상태 업데이트
            # (LangGraphAdapter 실행 결과에서 상태 추출)
            workflow_result = self._langgraph_adapter.execute(
                user_message=message,
                session_id=session_id,
                initial_state=current_state
            )

            current_state = {
                "is_human_required_flow": workflow_result.is_human_required_flow,
                "customer_consent_received": workflow_result.metadata.get("customer_consent_received", False),
                "collected_info": workflow_result.collected_info,
                "context_intent": workflow_result.context_intent
            }

        return results

    def get_all_nodes(self) -> List[str]:
        """워크플로우의 모든 노드 목록 반환."""
        return [
            "triage_agent",
            "answer_agent",
            "consent_check",
            "waiting_agent",
            "chat_db_storage",
            "summary_agent",
            "human_transfer"
        ]

    def get_node_description(self, node_name: str) -> str:
        """노드 설명 반환."""
        descriptions = {
            "triage_agent": "의도 분류 및 RAG 검색을 수행하여 응답 전략 결정",
            "answer_agent": "triage 결과에 따른 응답 생성",
            "consent_check": "상담사 연결 동의 확인 (룰 베이스)",
            "waiting_agent": "상담사 연결을 위한 고객 정보 수집",
            "chat_db_storage": "대화 내용 및 수집된 정보 DB 저장",
            "summary_agent": "수집된 정보 요약 생성",
            "human_transfer": "상담사에게 세션 이관 처리"
        }
        return descriptions.get(node_name, "알 수 없는 노드")

    def validate_scenario(
        self,
        scenario_name: str,
        messages: List[str],
        expected_final_flow_type: str,
        expected_info_complete: bool = False
    ) -> Dict[str, Any]:
        """시나리오 검증.

        Args:
            scenario_name: 시나리오 이름
            messages: 사용자 메시지 리스트
            expected_final_flow_type: 예상 최종 플로우 타입
            expected_info_complete: 예상 정보 수집 완료 여부

        Returns:
            검증 결과 딕셔너리
        """
        self._ensure_initialized()

        try:
            # 멀티턴 실행
            workflow_results = self._langgraph_adapter.execute_multi_turn(
                messages=messages,
                session_id=f"scenario_{scenario_name}"
            )

            if not workflow_results:
                return {
                    "scenario": scenario_name,
                    "passed": False,
                    "error": "실행 결과 없음"
                }

            final_result = workflow_results[-1]

            # 검증
            flow_type_match = final_result.triage_decision == expected_final_flow_type or \
                            (expected_final_flow_type == "HUMAN_REQUIRED" and final_result.is_human_required_flow)

            info_complete_match = final_result.info_collection_complete == expected_info_complete

            passed = flow_type_match and info_complete_match

            return {
                "scenario": scenario_name,
                "passed": passed,
                "num_turns": len(workflow_results),
                "flow_type_match": flow_type_match,
                "info_complete_match": info_complete_match,
                "actual_flow_type": final_result.triage_decision,
                "actual_info_complete": final_result.info_collection_complete,
                "collected_info": final_result.collected_info
            }

        except Exception as e:
            return {
                "scenario": scenario_name,
                "passed": False,
                "error": str(e)
            }
