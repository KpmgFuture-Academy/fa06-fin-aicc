# e2e_evaluation_pipeline/adapters/slot_adapter.py
"""Slot Filling 모듈과 E2E 평가 파이프라인 연동 어댑터.

실제 waiting_agent의 슬롯 수집 로직을 호출하여
슬롯 추출 결과를 평가 가능한 형태로 변환합니다.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SlotExtractionResult:
    """슬롯 추출 결과"""
    category: str
    domain: str
    required_slots: List[str]
    optional_slots: List[str]
    extracted_slots: Dict[str, Any]
    missing_slots: List[str]
    is_complete: bool
    question: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SlotDefinition:
    """슬롯 정의"""
    name: str
    label: str
    question: str
    validation: Optional[str] = None
    is_required: bool = True


class SlotAdapter:
    """Slot Filling 어댑터.

    E2E 평가 파이프라인에서 실제 슬롯 시스템을 호출하고
    결과를 평가 가능한 형태로 변환합니다.
    """

    def __init__(self):
        self._slot_loader = None
        self._initialized = False

    def _ensure_initialized(self):
        """슬롯 로더 지연 초기화"""
        if self._initialized:
            return

        try:
            from ai_engine.graph.utils.slot_loader import get_slot_loader
            self._slot_loader = get_slot_loader()
            self._initialized = True
            logger.info("슬롯 로더 초기화 완료")
        except Exception as e:
            logger.error(f"슬롯 로더 초기화 실패: {e}")
            raise RuntimeError(f"슬롯 로더 초기화 실패: {e}")

    def get_slots_for_category(self, category: str) -> Tuple[List[str], List[str]]:
        """카테고리에 필요한 슬롯 목록 반환.

        Args:
            category: 38개 카테고리 중 하나

        Returns:
            (required_slots, optional_slots) 튜플
        """
        self._ensure_initialized()
        return self._slot_loader.get_slots_for_category(category)

    def extract_slots(
        self,
        conversation_history: List[Dict[str, str]],
        current_message: str,
        category: str,
        existing_slots: Optional[Dict[str, Any]] = None
    ) -> SlotExtractionResult:
        """대화에서 슬롯 추출.

        Args:
            conversation_history: 대화 히스토리
            current_message: 현재 사용자 메시지
            category: 카테고리
            existing_slots: 이미 수집된 슬롯

        Returns:
            SlotExtractionResult: 추출 결과
        """
        self._ensure_initialized()

        try:
            # 필수/선택 슬롯 가져오기
            required_slots, optional_slots = self._slot_loader.get_slots_for_category(category)

            # 도메인 정보
            domain_code = self._slot_loader.get_domain_by_category(category)
            domain_name = self._slot_loader.get_domain_name(domain_code) if domain_code else "기타"

            # 기존 슬롯 복사
            extracted = dict(existing_slots) if existing_slots else {}

            # 대화에서 슬롯 추출 시도 (간단한 규칙 기반)
            # 실제로는 waiting_agent에서 LLM을 사용하지만,
            # 평가용으로는 규칙 기반으로 먼저 시도
            new_extractions = self._extract_from_text(
                conversation_history,
                current_message,
                required_slots + optional_slots
            )

            # 기존 슬롯에 새로 추출된 것 병합
            for slot_name, value in new_extractions.items():
                if value and not extracted.get(slot_name):
                    extracted[slot_name] = value

            # 누락된 필수 슬롯 확인
            missing = self._slot_loader.get_missing_required_slots(category, extracted)

            # 완료 여부
            is_complete = len(missing) == 0

            # 다음 질문 생성 (누락된 슬롯이 있는 경우)
            question = None
            if missing:
                question = self._slot_loader.get_slot_question(missing[0])

            return SlotExtractionResult(
                category=category,
                domain=domain_name,
                required_slots=required_slots,
                optional_slots=optional_slots,
                extracted_slots=extracted,
                missing_slots=missing,
                is_complete=is_complete,
                question=question
            )

        except Exception as e:
            logger.error(f"슬롯 추출 오류: {e}", exc_info=True)
            return SlotExtractionResult(
                category=category,
                domain="기타",
                required_slots=[],
                optional_slots=[],
                extracted_slots={},
                missing_slots=[],
                is_complete=False,
                error=str(e)
            )

    def _extract_from_text(
        self,
        conversation_history: List[Dict[str, str]],
        current_message: str,
        slot_names: List[str]
    ) -> Dict[str, Any]:
        """텍스트에서 규칙 기반 슬롯 추출.

        실제 waiting_agent는 LLM을 사용하지만,
        평가용 어댑터에서는 간단한 규칙 기반 추출을 먼저 시도합니다.
        """
        extracted = {}

        # 모든 사용자 메시지 합치기
        all_text = current_message
        for msg in conversation_history:
            if msg.get("role") == "user":
                all_text += " " + msg.get("message", "")

        all_text = all_text.lower()

        # 카드 뒤 4자리 추출 (정규식)
        if "card_last_4_digits" in slot_names:
            import re
            matches = re.findall(r'\b(\d{4})\b', all_text)
            if matches:
                # 가장 마지막 4자리 숫자 사용
                extracted["card_last_4_digits"] = matches[-1]

        # 금액 추출
        amount_slots = ["transaction_amount", "fraud_amount", "desired_loan_amount",
                       "desired_amount", "payment_amount", "withdrawal_amount"]
        for slot in amount_slots:
            if slot in slot_names and slot not in extracted:
                import re
                # "10만원", "100,000원", "10만 원" 등의 패턴
                matches = re.findall(r'(\d+(?:,\d+)?(?:만)?)\s*원', all_text)
                if matches:
                    extracted[slot] = matches[-1] + "원"

        # 날짜 추출
        date_slots = ["loss_date", "fraud_date", "transaction_date", "error_date"]
        for slot in date_slots:
            if slot in slot_names and slot not in extracted:
                import re
                # "12월 8일", "2024-12-08", "어제", "오늘" 등
                date_patterns = [
                    r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',  # 2024-12-08
                    r'(\d{1,2}월\s*\d{1,2}일)',  # 12월 8일
                ]
                for pattern in date_patterns:
                    matches = re.findall(pattern, all_text)
                    if matches:
                        extracted[slot] = matches[-1]
                        break

                # 상대적 날짜
                if slot not in extracted:
                    if "어제" in all_text:
                        extracted[slot] = "어제"
                    elif "오늘" in all_text:
                        extracted[slot] = "오늘"
                    elif "그제" in all_text or "그저께" in all_text:
                        extracted[slot] = "그저께"

        return extracted

    def evaluate_extraction(
        self,
        result: SlotExtractionResult,
        expected_slots: Dict[str, Any]
    ) -> Dict[str, Any]:
        """슬롯 추출 결과 평가.

        Args:
            result: 슬롯 추출 결과
            expected_slots: 기대하는 슬롯 값

        Returns:
            평가 결과 딕셔너리
        """
        evaluation = {
            "extraction_rate": 0.0,
            "accuracy": 0.0,
            "completion_status": result.is_complete,
            "matched_slots": [],
            "missed_slots": [],
            "wrong_slots": []
        }

        if not expected_slots:
            return evaluation

        expected_keys = set(expected_slots.keys())
        extracted_keys = set(result.extracted_slots.keys())

        # 추출률: 기대 슬롯 중 추출된 비율
        if expected_keys:
            matched = expected_keys & extracted_keys
            evaluation["extraction_rate"] = len(matched) / len(expected_keys)
            evaluation["matched_slots"] = list(matched)
            evaluation["missed_slots"] = list(expected_keys - extracted_keys)

        # 정확도: 추출된 값 중 정확한 비율
        correct_count = 0
        for key in extracted_keys:
            if key in expected_slots:
                expected_val = str(expected_slots[key]).lower().strip()
                extracted_val = str(result.extracted_slots[key]).lower().strip()

                # 부분 일치도 허용 (포함 관계)
                if expected_val == extracted_val or expected_val in extracted_val or extracted_val in expected_val:
                    correct_count += 1
                else:
                    evaluation["wrong_slots"].append({
                        "slot": key,
                        "expected": expected_slots[key],
                        "extracted": result.extracted_slots[key]
                    })

        if extracted_keys:
            evaluation["accuracy"] = correct_count / len(extracted_keys)

        return evaluation

    def get_slot_definition(self, slot_name: str) -> Optional[SlotDefinition]:
        """슬롯 정의 반환.

        Args:
            slot_name: 슬롯 이름

        Returns:
            SlotDefinition 또는 None
        """
        self._ensure_initialized()

        label = self._slot_loader.get_slot_label(slot_name)
        question = self._slot_loader.get_slot_question(slot_name)

        if not label or label == slot_name:
            return None

        return SlotDefinition(
            name=slot_name,
            label=label,
            question=question
        )

    def get_all_categories(self) -> List[str]:
        """모든 카테고리 목록 반환."""
        self._ensure_initialized()
        return self._slot_loader.get_all_categories()

    def get_all_domains(self) -> Dict[str, str]:
        """모든 도메인 목록 반환 (코드: 이름)."""
        self._ensure_initialized()

        # slot_loader에서 도메인 정보 가져오기
        domains = {}
        for domain_code in ["SEC_CARD", "LIMIT_AUTH", "PAY_BILL", "DELINQ",
                          "LOAN", "BENEFIT", "UTILITY", "DOC_TAX"]:
            name = self._slot_loader.get_domain_name(domain_code)
            if name:
                domains[domain_code] = name

        return domains

    def simulate_multi_turn_collection(
        self,
        category: str,
        user_responses: List[str]
    ) -> List[SlotExtractionResult]:
        """멀티턴 슬롯 수집 시뮬레이션.

        Args:
            category: 카테고리
            user_responses: 사용자 응답 리스트

        Returns:
            각 턴별 추출 결과 리스트
        """
        results = []
        conversation_history = []
        current_slots = {}

        for i, response in enumerate(user_responses):
            # 추출 수행
            result = self.extract_slots(
                conversation_history=conversation_history,
                current_message=response,
                category=category,
                existing_slots=current_slots
            )
            results.append(result)

            # 히스토리 업데이트
            conversation_history.append({"role": "user", "message": response})
            if result.question:
                conversation_history.append({"role": "assistant", "message": result.question})

            # 슬롯 업데이트
            current_slots = result.extracted_slots.copy()

            # 완료 시 종료
            if result.is_complete:
                break

        return results
