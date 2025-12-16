"""
Slot Filling Metrics Evaluation
===============================

대기시간 에이전트 (Waiting Agent) 정보 수집 성능 평가

평가 지표:
    - Slot Completion Rate: 필수 정보 수집 완료율
    - Field Extraction Accuracy: 필드별 추출 정확도
    - Average Turns: 정보 수집 완료까지 평균 턴 수
    - Wrong Assignment Rate: 잘못된 필드 할당 비율
    - Failure to Transfer Rate: 수집 실패로 이관된 비율
    - Duplicate Question Rate: 중복 질문 비율
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class SlotTestCase:
    """Slot Filling 테스트 케이스"""
    dialogue_id: str
    dialogue_turns: List[Dict[str, str]]  # [{"role": "user/assistant", "content": "..."}]
    expected_slots: Dict[str, str]  # {"customer_name": "홍길동", "inquiry_type": "카드 분실", ...}
    final_transferred: bool = False  # 최종 상담사 이관 여부


@dataclass
class SlotFillingResult:
    """Slot Filling 결과"""
    dialogue_id: str
    extracted_slots: Dict[str, str]  # 추출된 슬롯 정보
    num_turns: int  # 소요된 턴 수
    completion_status: bool  # 완료 여부
    transferred_due_to_failure: bool = False  # 실패로 인한 이관 여부
    duplicate_questions: List[str] = field(default_factory=list)  # 중복 질문 목록


class SlotFillingMetrics(BaseMetrics):
    """Slot Filling 성능 평가 메트릭"""

    # 필수 슬롯 필드
    REQUIRED_FIELDS = ["customer_name", "inquiry_type", "inquiry_detail"]

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.slot_filling)

    @property
    def module_name(self) -> str:
        return "Slot Filling"

    def evaluate(self, data: List[Tuple[SlotTestCase, SlotFillingResult]]) -> EvaluationResult:
        """
        Slot Filling 성능 평가 실행

        Args:
            data: [(테스트케이스, 결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산
        completion_rates = []
        field_accuracies = {field: [] for field in self.REQUIRED_FIELDS}
        turn_counts = []
        wrong_assignments = []
        failure_transfers = []
        duplicate_rates = []

        for test_case, result in data:
            try:
                # Slot Completion Rate
                completion = self._calculate_completion_rate(
                    test_case.expected_slots,
                    result.extracted_slots
                )
                completion_rates.append(completion)

                # Field-specific Accuracy
                for field in self.REQUIRED_FIELDS:
                    if field in test_case.expected_slots:
                        accuracy = self._calculate_field_accuracy(
                            test_case.expected_slots.get(field, ""),
                            result.extracted_slots.get(field, "")
                        )
                        field_accuracies[field].append(accuracy)

                # Turn Count
                turn_counts.append(result.num_turns)

                # Wrong Assignment Rate
                wrong_rate = self._calculate_wrong_assignment_rate(
                    test_case.expected_slots,
                    result.extracted_slots
                )
                wrong_assignments.append(wrong_rate)

                # Failure to Transfer
                if result.transferred_due_to_failure:
                    failure_transfers.append(1)
                else:
                    failure_transfers.append(0)

                # Duplicate Question Rate
                if test_case.dialogue_turns:
                    dup_rate = self._calculate_duplicate_question_rate(
                        test_case.dialogue_turns,
                        result.duplicate_questions
                    )
                    duplicate_rates.append(dup_rate)

            except Exception as e:
                self.errors.append(f"Error processing dialogue {test_case.dialogue_id}: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(completion_rates)
        }

        # Slot Completion Rate
        if completion_rates:
            avg_completion = sum(completion_rates) / len(completion_rates)
            self.results.append(self._create_metric_result(
                "completion_rate", avg_completion,
                details={
                    "fully_completed": sum(1 for c in completion_rates if c == 100),
                    "partial": sum(1 for c in completion_rates if 0 < c < 100),
                    "none": sum(1 for c in completion_rates if c == 0)
                }
            ))
            summary["avg_completion_rate"] = avg_completion

        # Field-specific Accuracies
        for field_name, accuracies in field_accuracies.items():
            if accuracies:
                avg_acc = sum(accuracies) / len(accuracies)
                metric_key = f"{field_name}_accuracy"

                # KPI에 정의된 필드만 추가
                if metric_key in self.kpi_metrics:
                    self.results.append(self._create_metric_result(
                        metric_key, avg_acc
                    ))
                summary[f"avg_{field_name}_accuracy"] = avg_acc

        # Average Turns
        if turn_counts:
            avg_turns = sum(turn_counts) / len(turn_counts)
            self.results.append(self._create_metric_result(
                "avg_turns", avg_turns,
                details={
                    "min": min(turn_counts),
                    "max": max(turn_counts),
                    "distribution": self._get_turn_distribution(turn_counts)
                }
            ))
            summary["avg_turns"] = avg_turns

        # Wrong Assignment Rate
        if wrong_assignments:
            avg_wrong = sum(wrong_assignments) / len(wrong_assignments)
            self.results.append(self._create_metric_result(
                "wrong_assignment_rate", avg_wrong
            ))

        # Failure to Transfer Rate
        if failure_transfers:
            failure_rate = (sum(failure_transfers) / len(failure_transfers)) * 100
            self.results.append(self._create_metric_result(
                "failure_to_transfer_rate", failure_rate
            ))
            summary["failure_to_transfer_rate"] = failure_rate

        # Duplicate Question Rate
        if duplicate_rates:
            avg_dup = sum(duplicate_rates) / len(duplicate_rates)
            self.results.append(self._create_metric_result(
                "duplicate_question_rate", avg_dup
            ))

        return self._create_evaluation_result(start_time, summary)

    def _calculate_completion_rate(
        self,
        expected: Dict[str, str],
        extracted: Dict[str, str]
    ) -> float:
        """슬롯 완료율 계산"""
        if not expected:
            return 100.0

        filled_count = 0
        for field, expected_value in expected.items():
            if field in extracted and extracted[field]:
                filled_count += 1

        return (filled_count / len(expected)) * 100

    def _calculate_field_accuracy(
        self,
        expected: str,
        extracted: str
    ) -> float:
        """필드별 추출 정확도 계산"""
        if not expected:
            return 100.0 if not extracted else 0.0

        if not extracted:
            return 0.0

        # 정규화 후 비교
        expected_norm = expected.strip().lower()
        extracted_norm = extracted.strip().lower()

        # 완전 일치
        if expected_norm == extracted_norm:
            return 100.0

        # 부분 일치 (포함 관계)
        if expected_norm in extracted_norm or extracted_norm in expected_norm:
            return 80.0

        # 토큰 기반 유사도
        expected_tokens = set(expected_norm.split())
        extracted_tokens = set(extracted_norm.split())

        if not expected_tokens:
            return 0.0

        overlap = len(expected_tokens & extracted_tokens)
        return (overlap / len(expected_tokens)) * 100

    def _calculate_wrong_assignment_rate(
        self,
        expected: Dict[str, str],
        extracted: Dict[str, str]
    ) -> float:
        """잘못된 필드 할당 비율"""
        if not extracted:
            return 0.0

        wrong_count = 0
        for field, value in extracted.items():
            if not value:
                continue

            # 다른 필드에 있어야 할 값이 이 필드에 할당된 경우
            for other_field, expected_value in expected.items():
                if other_field != field and expected_value:
                    if self._is_similar(value, expected_value) and field in expected:
                        if not self._is_similar(value, expected.get(field, "")):
                            wrong_count += 1
                            break

        total_filled = sum(1 for v in extracted.values() if v)
        if total_filled == 0:
            return 0.0

        return (wrong_count / total_filled) * 100

    def _is_similar(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """두 텍스트의 유사성 판단"""
        if not text1 or not text2:
            return False

        text1_norm = text1.strip().lower()
        text2_norm = text2.strip().lower()

        if text1_norm == text2_norm:
            return True

        # 토큰 기반 유사도
        tokens1 = set(text1_norm.split())
        tokens2 = set(text2_norm.split())

        if not tokens1 or not tokens2:
            return False

        overlap = len(tokens1 & tokens2)
        similarity = overlap / max(len(tokens1), len(tokens2))

        return similarity >= threshold

    def _calculate_duplicate_question_rate(
        self,
        dialogue_turns: List[Dict[str, str]],
        duplicate_questions: List[str]
    ) -> float:
        """중복 질문 비율"""
        # assistant 턴 수 계산
        assistant_turns = [t for t in dialogue_turns if t.get("role") == "assistant"]

        if not assistant_turns:
            return 0.0

        return (len(duplicate_questions) / len(assistant_turns)) * 100

    def _get_turn_distribution(self, turn_counts: List[int]) -> Dict[str, int]:
        """턴 수 분포"""
        distribution = defaultdict(int)
        for count in turn_counts:
            if count <= 2:
                distribution["1-2"] += 1
            elif count <= 3:
                distribution["3"] += 1
            elif count <= 5:
                distribution["4-5"] += 1
            else:
                distribution["6+"] += 1

        return dict(distribution)


def analyze_slot_filling_dialogue(
    dialogue: List[Dict[str, str]],
    expected_slots: Dict[str, str]
) -> SlotFillingResult:
    """
    대화에서 Slot Filling 결과 분석

    Args:
        dialogue: 대화 턴 리스트
        expected_slots: 예상 슬롯 값
    """
    import re

    extracted_slots = {}
    num_turns = len([t for t in dialogue if t.get("role") == "user"])
    duplicate_questions = []

    # 간단한 패턴 기반 추출 (실제로는 LLM 사용)
    patterns = {
        "customer_name": [
            r"(?:제\s*이름은|저는)\s*([가-힣]{2,4})(?:입니다|이에요|예요)?",
            r"([가-힣]{2,4})(?:라고\s*합니다|입니다)"
        ],
        "inquiry_type": [
            r"(카드\s*분실|결제\s*오류|한도\s*조정|포인트\s*문의|해지\s*문의)",
            r"(분실|도난|결제|한도|포인트|해지)"
        ],
        "inquiry_detail": [
            r"(?:상세|자세한\s*내용|문의\s*내용)[은는:\s]*(.+)",
        ]
    }

    for turn in dialogue:
        if turn.get("role") != "user":
            continue

        content = turn.get("content", "")

        for field, field_patterns in patterns.items():
            if field in extracted_slots:
                continue

            for pattern in field_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    extracted_slots[field] = match.group(1).strip()
                    break

    # 완료 여부 판단
    completion_status = all(
        field in extracted_slots and extracted_slots[field]
        for field in expected_slots.keys()
    )

    return SlotFillingResult(
        dialogue_id="",
        extracted_slots=extracted_slots,
        num_turns=num_turns,
        completion_status=completion_status,
        duplicate_questions=duplicate_questions
    )
