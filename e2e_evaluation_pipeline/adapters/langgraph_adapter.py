# e2e_evaluation_pipeline/adapters/langgraph_adapter.py
"""LangGraph 워크플로우와 E2E 평가 파이프라인 연동 어댑터.

실제 LangGraph 워크플로우를 실행하고 결과를 평가 가능한 형태로 변환합니다.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecutionResult:
    """워크플로우 실행 결과"""
    session_id: str
    user_message: str
    ai_message: str
    triage_decision: str
    context_intent: Optional[str] = None
    is_human_required_flow: bool = False
    info_collection_complete: bool = False
    collected_info: Dict[str, Any] = field(default_factory=dict)
    source_documents: List[Dict] = field(default_factory=list)
    node_sequence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class LangGraphAdapter:
    """LangGraph 워크플로우 어댑터.

    E2E 평가 파이프라인에서 실제 LangGraph 워크플로우를 호출하고
    결과를 평가 가능한 형태로 변환합니다.
    """

    def __init__(self):
        self._workflow = None
        self._initialized = False

    def _ensure_initialized(self):
        """워크플로우 지연 초기화"""
        if self._initialized:
            return

        try:
            from ai_engine.graph.workflow import build_workflow
            self._workflow = build_workflow()
            self._initialized = True
            logger.info("LangGraph 워크플로우 초기화 완료")
        except Exception as e:
            logger.error(f"LangGraph 워크플로우 초기화 실패: {e}")
            raise RuntimeError(f"워크플로우 초기화 실패: {e}")

    def execute(
        self,
        user_message: str,
        session_id: str = "eval_session",
        conversation_history: Optional[List[Dict]] = None,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResult:
        """워크플로우 실행.

        Args:
            user_message: 사용자 메시지
            session_id: 세션 ID
            conversation_history: 이전 대화 히스토리
            initial_state: 초기 상태 (이전 턴의 상태 유지용)

        Returns:
            WorkflowExecutionResult: 실행 결과
        """
        self._ensure_initialized()

        # 초기 상태 구성
        state = {
            "session_id": session_id,
            "user_message": user_message,
            "conversation_history": conversation_history or [],
            "ai_message": "",
            "triage_decision": "",
            "context_intent": None,
            "is_human_required_flow": False,
            "customer_consent_received": False,
            "info_collection_complete": False,
            "collected_info": {},
            "source_documents": [],
            "metadata": {}
        }

        # 이전 상태 병합 (멀티턴 대화용)
        if initial_state:
            for key in ["is_human_required_flow", "customer_consent_received",
                       "collected_info", "context_intent"]:
                if key in initial_state:
                    state[key] = initial_state[key]

        try:
            # 워크플로우 실행
            result_state = self._workflow.invoke(state)

            # 노드 시퀀스 추출 (실행된 노드들)
            node_sequence = self._extract_node_sequence(result_state)

            return WorkflowExecutionResult(
                session_id=session_id,
                user_message=user_message,
                ai_message=result_state.get("ai_message", ""),
                triage_decision=result_state.get("triage_decision", ""),
                context_intent=result_state.get("context_intent"),
                is_human_required_flow=result_state.get("is_human_required_flow", False),
                info_collection_complete=result_state.get("info_collection_complete", False),
                collected_info=result_state.get("collected_info", {}),
                source_documents=result_state.get("source_documents", []),
                node_sequence=node_sequence,
                metadata=result_state.get("metadata", {})
            )

        except Exception as e:
            logger.error(f"워크플로우 실행 오류: {e}", exc_info=True)
            return WorkflowExecutionResult(
                session_id=session_id,
                user_message=user_message,
                ai_message="",
                triage_decision="ERROR",
                error=str(e)
            )

    def execute_multi_turn(
        self,
        messages: List[str],
        session_id: str = "eval_session"
    ) -> List[WorkflowExecutionResult]:
        """멀티턴 대화 실행.

        Args:
            messages: 사용자 메시지 리스트 (순서대로)
            session_id: 세션 ID

        Returns:
            List[WorkflowExecutionResult]: 각 턴별 실행 결과
        """
        results = []
        conversation_history = []
        current_state = None

        for i, message in enumerate(messages):
            logger.info(f"멀티턴 대화 턴 {i+1}/{len(messages)}: {message[:50]}...")

            # 워크플로우 실행
            result = self.execute(
                user_message=message,
                session_id=session_id,
                conversation_history=conversation_history,
                initial_state=current_state
            )
            results.append(result)

            # 대화 히스토리 업데이트
            conversation_history.append({"role": "user", "message": message})
            if result.ai_message:
                conversation_history.append({"role": "assistant", "message": result.ai_message})

            # 다음 턴을 위한 상태 저장
            current_state = {
                "is_human_required_flow": result.is_human_required_flow,
                "customer_consent_received": result.metadata.get("customer_consent_received", False),
                "collected_info": result.collected_info,
                "context_intent": result.context_intent
            }

            # 정보 수집 완료 시 종료
            if result.info_collection_complete:
                logger.info(f"정보 수집 완료 - 턴 {i+1}에서 종료")
                break

        return results

    def _extract_node_sequence(self, state: Dict[str, Any]) -> List[str]:
        """실행된 노드 시퀀스 추출.

        state의 metadata나 플래그를 기반으로 실행된 노드들을 추론합니다.
        """
        sequence = []

        is_human_required = state.get("is_human_required_flow", False)
        customer_consent = state.get("customer_consent_received", False)
        info_complete = state.get("info_collection_complete", False)
        triage_decision = state.get("triage_decision", "")

        if is_human_required:
            if customer_consent:
                sequence.append("waiting_agent")
                sequence.append("chat_db_storage")
                if info_complete:
                    sequence.append("summary_agent")
                    sequence.append("human_transfer")
            else:
                sequence.append("consent_check")
                if triage_decision:  # 동의 안 함 → triage로 돌아감
                    sequence.append("triage_agent")
                    sequence.append("answer_agent")
                    sequence.append("chat_db_storage")
        else:
            sequence.append("triage_agent")
            sequence.append("answer_agent")
            sequence.append("chat_db_storage")

        return sequence

    def get_expected_flow(self, triage_decision: str, is_human_required: bool = False) -> List[str]:
        """예상 노드 흐름 반환.

        Args:
            triage_decision: 판단 결과 (SIMPLE_ANSWER, AUTO_ANSWER, NEED_MORE_INFO, HUMAN_REQUIRED)
            is_human_required: HUMAN_REQUIRED 플로우 여부

        Returns:
            List[str]: 예상 노드 시퀀스
        """
        if triage_decision == "HUMAN_REQUIRED" or is_human_required:
            return [
                "consent_check",
                "waiting_agent",
                "chat_db_storage",
                "summary_agent",
                "human_transfer"
            ]
        else:
            return [
                "triage_agent",
                "answer_agent",
                "chat_db_storage"
            ]
