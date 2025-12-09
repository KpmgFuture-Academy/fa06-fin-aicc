"""
Data Loader for E2E Evaluation Pipeline
========================================

샘플 데이터셋 로더
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class DataLoader:
    """평가용 데이터 로더"""

    def __init__(self, datasets_dir: Optional[Path] = None):
        self.datasets_dir = datasets_dir or Path(__file__).parent

    def load_stt_test_data(self) -> Dict[str, Any]:
        """STT 테스트 데이터 로드"""
        path = self.datasets_dir / "stt_test" / "test_data.json"
        return self._load_json(path)

    def load_intent_test_data(self) -> Dict[str, Any]:
        """Intent 테스트 데이터 로드"""
        path = self.datasets_dir / "intent_test" / "test_data.json"
        return self._load_json(path)

    def load_golden_qa_data(self) -> Dict[str, Any]:
        """Golden QA 데이터 로드"""
        path = self.datasets_dir / "golden_qa" / "qa_set.json"
        return self._load_json(path)

    def load_slot_test_data(self) -> Dict[str, Any]:
        """Slot Filling 테스트 데이터 로드"""
        path = self.datasets_dir / "slot_test" / "dialogues.json"
        return self._load_json(path)

    def load_summary_test_data(self) -> Dict[str, Any]:
        """Summary 테스트 데이터 로드"""
        path = self.datasets_dir / "summary_test" / "test_data.json"
        return self._load_json(path)

    def load_flow_test_data(self) -> Dict[str, Any]:
        """Flow 테스트 데이터 로드"""
        path = self.datasets_dir / "flow_test" / "expected_flows.json"
        return self._load_json(path)

    def load_e2e_scenarios(self) -> Dict[str, Any]:
        """E2E 시나리오 데이터 로드"""
        path = self.datasets_dir / "e2e_test" / "scenarios.json"
        return self._load_json(path)

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """모든 테스트 데이터 로드"""
        return {
            "stt": self.load_stt_test_data(),
            "intent": self.load_intent_test_data(),
            "rag": self.load_golden_qa_data(),
            "slot_filling": self.load_slot_test_data(),
            "summary": self.load_summary_test_data(),
            "flow": self.load_flow_test_data(),
            "e2e": self.load_e2e_scenarios()
        }

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """JSON 파일 로드"""
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)


def get_sample_stt_pairs() -> List[tuple]:
    """
    STT 평가용 (reference, hypothesis) 쌍 생성

    Returns:
        List[Tuple[str, str]]: [(reference, hypothesis), ...]
    """
    loader = DataLoader()
    data = loader.load_stt_test_data()

    pairs = []
    for case in data.get("test_cases", []):
        pairs.append((case["reference"], case["hypothesis"]))

    return pairs


def get_sample_intent_data():
    """
    Intent 평가용 데이터 생성

    Returns:
        List[Tuple[IntentTestCase, IntentPrediction]]
    """
    from ..metrics.intent_metrics import IntentTestCase, IntentPrediction

    loader = DataLoader()
    data = loader.load_intent_test_data()
    labels = data.get("labels", [])

    # 샘플 예측 결과 시뮬레이션
    results = []
    for case in data.get("test_cases", []):
        test_case = IntentTestCase(
            text=case["text"],
            true_label=case["label"],
            domain=case.get("domain")
        )

        # 시뮬레이션: 90% 확률로 정답 예측
        import random
        if random.random() < 0.9:
            pred_label = case["label"]
            confidence = random.uniform(0.85, 0.99)
        else:
            pred_label = random.choice(labels)
            confidence = random.uniform(0.3, 0.7)

        # Top-3 생성
        top_k = [(pred_label, confidence)]
        other_labels = [l for l in labels if l != pred_label]
        for _ in range(2):
            if other_labels:
                other = random.choice(other_labels)
                other_labels.remove(other)
                top_k.append((other, random.uniform(0.1, confidence * 0.8)))

        prediction = IntentPrediction(
            predicted_label=pred_label,
            confidence=confidence,
            top_k_predictions=top_k
        )

        results.append((test_case, prediction))

    return results


def get_sample_slot_data():
    """
    Slot Filling 평가용 데이터 생성

    Returns:
        List[Tuple[SlotTestCase, SlotFillingResult]]
    """
    from ..metrics.slot_metrics import SlotTestCase, SlotFillingResult

    loader = DataLoader()
    data = loader.load_slot_test_data()

    results = []
    for case in data.get("test_cases", []):
        test_case = SlotTestCase(
            dialogue_id=case["dialogue_id"],
            dialogue_turns=case["dialogue_turns"],
            expected_slots=case["expected_slots"],
            final_transferred=case.get("final_transferred", False)
        )

        # 시뮬레이션: 대부분의 슬롯을 정확히 추출
        import random
        extracted = {}
        for field, value in case["expected_slots"].items():
            if random.random() < 0.85:  # 85% 정확도
                extracted[field] = value
            elif random.random() < 0.5:
                extracted[field] = value[:len(value)//2]  # 부분 추출

        result = SlotFillingResult(
            dialogue_id=case["dialogue_id"],
            extracted_slots=extracted,
            num_turns=len([t for t in case["dialogue_turns"] if t["role"] == "user"]),
            completion_status=len(extracted) == len(case["expected_slots"]),
            transferred_due_to_failure=case.get("final_transferred", False)
        )

        results.append((test_case, result))

    return results


def get_sample_summary_data():
    """
    Summary 평가용 데이터 생성

    Returns:
        List[Dict]: Summary 테스트 데이터
    """
    from ..metrics.summary_metrics import SummaryTestCase, SummaryResult

    loader = DataLoader()
    data = loader.load_summary_test_data()

    results = []
    for case in data.get("test_cases", []):
        test_case = SummaryTestCase(
            dialogue=case["dialogue"],
            reference_summary=case["reference_summary"],
            key_info=case.get("key_info", []),
            sentiment=case.get("sentiment")
        )

        # 시뮬레이션: 유사한 요약 생성
        import random
        words = case["reference_summary"].split()
        if random.random() < 0.9:
            # 약간 다른 요약
            gen_words = words.copy()
            if len(gen_words) > 3:
                idx = random.randint(0, len(gen_words) - 1)
                gen_words[idx] = "처리"
            generated = " ".join(gen_words)
        else:
            generated = case["reference_summary"]

        # 핵심 정보 추출
        extracted_info = [info for info in case.get("key_info", []) if random.random() < 0.85]

        result = SummaryResult(
            generated_summary=generated,
            extracted_key_info=extracted_info,
            predicted_sentiment=case.get("sentiment")
        )

        results.append((test_case, result))

    return results


def get_sample_flow_data():
    """
    Flow 평가용 데이터 생성

    Returns:
        List[Tuple[FlowTestCase, FlowResult]]: Flow 테스트 데이터
    """
    from ..metrics.flow_metrics import FlowTestCase, FlowResult, NodeTransition
    from datetime import datetime
    import random

    loader = DataLoader()
    data = loader.load_flow_test_data()

    results = []
    for case in data.get("test_cases", []):
        # FlowTestCase 생성 (flow_metrics.py 정의에 맞춤)
        test_case = FlowTestCase(
            session_id=case["flow_id"],
            input_message=case["scenario"],
            expected_flow=case["expected_flow"],
            expected_final_node=case["expected_flow"][-1] if case["expected_flow"] else "end"
        )

        # 시뮬레이션: 대부분 정확한 플로우
        if random.random() < 0.9:
            actual_flow = case["expected_flow"].copy()
        else:
            # 가끔 노드 하나 빠지거나 추가
            actual_flow = case["expected_flow"].copy()
            if len(actual_flow) > 2 and random.random() < 0.5:
                actual_flow.pop(random.randint(1, len(actual_flow) - 2))
            else:
                actual_flow.insert(random.randint(1, len(actual_flow) - 1), "triage_agent")

        # NodeTransition 리스트 생성
        transitions = []
        prev_node = "__start__"
        for node in actual_flow:
            expected_ms = case.get("expected_latency_ms", {}).get(node, 500)
            variation = random.uniform(0.8, 1.2)
            latency = expected_ms * variation

            transition = NodeTransition(
                from_node=prev_node,
                to_node=node,
                timestamp=datetime.now(),
                latency_ms=latency
            )
            transitions.append(transition)
            prev_node = node

        # FlowResult 생성 (flow_metrics.py 정의에 맞춤)
        result = FlowResult(
            session_id=case["flow_id"],
            actual_flow=actual_flow,
            transitions=transitions,
            final_node=actual_flow[-1] if actual_flow else "__end__",
            completed_successfully=True,
            fallback_triggered=False
        )

        results.append((test_case, result))

    return results
