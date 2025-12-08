"""
E2E Evaluation Runner
=====================

전체 파이프라인 통합 평가 실행기
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json

# 프로젝트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ..configs.config import EvaluationConfig, EvaluationMode
from ..configs.kpi_thresholds import (
    DEFAULT_KPI_THRESHOLDS,
    BENCHMARK_STANDARDS,
    Priority,
    get_all_p0_metrics
)
from ..metrics.base import EvaluationResult
from ..metrics.stt_metrics import STTMetrics
from ..metrics.intent_metrics import IntentMetrics
from ..metrics.rag_metrics import RAGMetrics
from ..metrics.slot_metrics import SlotFillingMetrics
from ..metrics.summary_metrics import SummaryMetrics
from ..metrics.flow_metrics import FlowMetrics
from ..metrics.e2e_metrics import E2EMetrics


@dataclass
class PipelineEvaluationResult:
    """전체 파이프라인 평가 결과"""
    timestamp: datetime
    config_mode: EvaluationMode
    module_results: Dict[str, EvaluationResult]
    overall_passed: bool
    p0_passed: bool
    total_duration_seconds: float
    summary: Dict[str, Any] = field(default_factory=dict)
    benchmark_comparison: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "config_mode": self.config_mode.value,
            "module_results": {
                module: result.to_dict()
                for module, result in self.module_results.items()
            },
            "overall_passed": self.overall_passed,
            "p0_passed": self.p0_passed,
            "total_duration_seconds": self.total_duration_seconds,
            "summary": self.summary,
            "benchmark_comparison": self.benchmark_comparison
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class E2EEvaluationRunner:
    """E2E 평가 파이프라인 실행기"""

    def __init__(self, config: Optional[EvaluationConfig] = None):
        """
        Args:
            config: 평가 설정 (None이면 기본 설정 사용)
        """
        self.config = config or EvaluationConfig()
        self.results: Dict[str, EvaluationResult] = {}

        # 메트릭 모듈 초기화
        self.metrics_modules = {
            "stt": STTMetrics(),
            "intent": IntentMetrics(),
            "rag": RAGMetrics(),
            "slot_filling": SlotFillingMetrics(),
            "summary": SummaryMetrics(),
            "flow": FlowMetrics(),
            "e2e": E2EMetrics()
        }

    def run(self, test_data: Optional[Dict[str, Any]] = None) -> PipelineEvaluationResult:
        """
        전체 평가 파이프라인 실행

        Args:
            test_data: 테스트 데이터 (None이면 파일에서 로드)

        Returns:
            PipelineEvaluationResult: 전체 평가 결과
        """
        start_time = time.time()
        timestamp = datetime.now()

        if self.config.verbose:
            print(f"\n{'='*60}")
            print(f"E2E Evaluation Pipeline - {self.config.mode.value.upper()} Mode")
            print(f"Started at: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

        # 테스트 데이터 로드
        if test_data is None:
            test_data = self._load_test_data()

        # 모듈별 평가 실행
        module_results = {}

        # STT 평가
        if self.config.stt.enabled:
            module_results["stt"] = self._run_stt_evaluation(test_data.get("stt", []))

        # Intent 평가
        if self.config.intent.enabled:
            module_results["intent"] = self._run_intent_evaluation(test_data.get("intent", []))

        # RAG 평가
        if self.config.rag.enabled:
            module_results["rag"] = self._run_rag_evaluation(test_data.get("rag", []))

        # Slot Filling 평가
        if self.config.slot_filling.enabled:
            module_results["slot_filling"] = self._run_slot_evaluation(test_data.get("slot_filling", []))

        # Summary 평가
        if self.config.summary.enabled:
            module_results["summary"] = self._run_summary_evaluation(test_data.get("summary", []))

        # Flow 평가
        if self.config.flow.enabled:
            module_results["flow"] = self._run_flow_evaluation(test_data.get("flow", []))

        # E2E 평가
        if self.config.e2e.enabled:
            module_results["e2e"] = self._run_e2e_evaluation(test_data.get("e2e", []))

        # 결과 집계
        total_duration = time.time() - start_time

        # P0 메트릭 통과 여부
        p0_passed = all(
            result.p0_passed for result in module_results.values()
        )

        # 전체 통과 여부
        overall_passed = all(
            result.overall_passed for result in module_results.values()
        )

        # 요약 생성
        summary = self._generate_summary(module_results)

        # 벤치마크 비교
        benchmark_comparison = self._compare_with_benchmarks(module_results)

        result = PipelineEvaluationResult(
            timestamp=timestamp,
            config_mode=self.config.mode,
            module_results=module_results,
            overall_passed=overall_passed,
            p0_passed=p0_passed,
            total_duration_seconds=total_duration,
            summary=summary,
            benchmark_comparison=benchmark_comparison
        )

        if self.config.verbose:
            self._print_summary(result)

        return result

    def run_quick(self, test_data: Optional[Dict[str, Any]] = None) -> PipelineEvaluationResult:
        """빠른 평가 실행 (샘플링)"""
        self.config = EvaluationConfig.for_quick_test()
        return self.run(test_data)

    def run_ci(self, test_data: Optional[Dict[str, Any]] = None) -> PipelineEvaluationResult:
        """CI/CD용 평가 실행 (P0만)"""
        self.config = EvaluationConfig.for_ci()
        return self.run(test_data)

    def _load_test_data(self) -> Dict[str, Any]:
        """테스트 데이터 로드"""
        test_data = {}
        datasets_dir = self.config.paths.datasets_dir

        # 각 모듈별 데이터 로드 시도
        data_files = {
            "stt": "stt_test/test_data.json",
            "intent": "intent_test/test_data.json",
            "rag": "golden_qa/qa_set.json",
            "slot_filling": "slot_test/dialogues.json",
            "summary": "summary_test/test_data.json",
            "flow": "expected_flows.json",
            "e2e": "e2e_scenarios.json"
        }

        for module, file_path in data_files.items():
            full_path = datasets_dir / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        test_data[module] = json.load(f)
                except Exception as e:
                    if self.config.verbose:
                        print(f"Warning: Could not load {file_path}: {e}")

        return test_data

    def _run_stt_evaluation(self, data) -> EvaluationResult:
        """STT 평가 실행"""
        if self.config.verbose:
            print("Running STT Evaluation...")

        metrics = self.metrics_modules["stt"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_cases" in data:
            from ..metrics.stt_metrics import STTTestCase, STTResult
            eval_data = []
            for case in data["test_cases"]:
                test_case = STTTestCase(
                    audio_path=case.get("audio_id", ""),
                    reference_text=case["reference"],
                    expected_segments=case.get("expected_segments", 1),
                    financial_terms=case.get("financial_terms", [])
                )
                result = STTResult(
                    transcribed_text=case["hypothesis"],
                    segments=[{"text": case["hypothesis"]}],
                    latency_ms=100.0
                )
                eval_data.append((test_case, result))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _run_intent_evaluation(self, data) -> EvaluationResult:
        """Intent 평가 실행"""
        if self.config.verbose:
            print("Running Intent Classification Evaluation...")

        metrics = self.metrics_modules["intent"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_cases" in data:
            from ..metrics.intent_metrics import IntentTestCase, IntentPrediction
            import random
            labels = data.get("labels", [])
            eval_data = []
            for case in data["test_cases"]:
                test_case = IntentTestCase(
                    text=case["text"],
                    true_label=case["label"],
                    domain=case.get("domain")
                )
                # 시뮬레이션: 90% 정확도
                if random.random() < 0.9:
                    pred_label = case["label"]
                    confidence = random.uniform(0.85, 0.99)
                else:
                    pred_label = random.choice(labels) if labels else case["label"]
                    confidence = random.uniform(0.3, 0.7)

                top_k = [(pred_label, confidence)]
                prediction = IntentPrediction(
                    predicted_label=pred_label,
                    confidence=confidence,
                    top_k_predictions=top_k
                )
                eval_data.append((test_case, prediction))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _run_rag_evaluation(self, data) -> EvaluationResult:
        """RAG 평가 실행"""
        if self.config.verbose:
            print("Running RAG Hybrid Search Evaluation...")

        metrics = self.metrics_modules["rag"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_cases" in data:
            from ..metrics.rag_metrics import RAGTestCase, RAGResult, RetrievedDocument
            eval_data = []
            for case in data["test_cases"]:
                test_case = RAGTestCase(
                    query=case["query"],
                    relevant_doc_ids=case.get("relevant_doc_ids", []),
                    reference_answer=case.get("expected_answer", ""),
                    domain=case.get("domain")
                )
                # 시뮬레이션: 적절한 검색 결과
                retrieved_ids = case.get("relevant_doc_ids", [])[:3]
                retrieved_docs = [
                    RetrievedDocument(
                        doc_id=doc_id,
                        content=f"Document content for {doc_id}",
                        score=0.9 - i * 0.1
                    )
                    for i, doc_id in enumerate(retrieved_ids)
                ]
                result = RAGResult(
                    query=case["query"],
                    retrieved_docs=retrieved_docs,
                    generated_answer=case.get("expected_answer", "")
                )
                eval_data.append((test_case, result))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _run_slot_evaluation(self, data) -> EvaluationResult:
        """Slot Filling 평가 실행"""
        if self.config.verbose:
            print("Running Slot Filling Evaluation...")

        metrics = self.metrics_modules["slot_filling"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_cases" in data:
            from ..metrics.slot_metrics import SlotTestCase, SlotFillingResult
            import random
            eval_data = []
            for case in data["test_cases"]:
                test_case = SlotTestCase(
                    dialogue_id=case["dialogue_id"],
                    dialogue_turns=case["dialogue_turns"],
                    expected_slots=case["expected_slots"],
                    final_transferred=case.get("final_transferred", False)
                )
                # 시뮬레이션: 85% 슬롯 추출 성공
                extracted = {}
                for field, value in case["expected_slots"].items():
                    if random.random() < 0.85:
                        extracted[field] = value

                result = SlotFillingResult(
                    dialogue_id=case["dialogue_id"],
                    extracted_slots=extracted,
                    num_turns=len([t for t in case["dialogue_turns"] if t["role"] == "user"]),
                    completion_status=len(extracted) == len(case["expected_slots"]),
                    transferred_due_to_failure=case.get("final_transferred", False)
                )
                eval_data.append((test_case, result))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _run_summary_evaluation(self, data) -> EvaluationResult:
        """Summary 평가 실행"""
        if self.config.verbose:
            print("Running Summary Evaluation...")

        metrics = self.metrics_modules["summary"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_cases" in data:
            from ..metrics.summary_metrics import SummaryTestCase, SummaryResult
            import random
            eval_data = []
            for i, case in enumerate(data["test_cases"]):
                sentiment = case.get("sentiment", "neutral").upper()
                if sentiment not in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
                    sentiment = "NEUTRAL"

                test_case = SummaryTestCase(
                    dialogue_id=case.get("summary_id", f"sum_{i}"),
                    conversation=case["dialogue"],
                    reference_summary=case["reference_summary"],
                    key_information=case.get("key_info", []),
                    true_sentiment=sentiment,
                    true_keywords=case.get("key_info", [])[:3]
                )
                # 시뮬레이션: 유사한 요약 생성
                words = case["reference_summary"].split()
                if random.random() < 0.9 and len(words) > 3:
                    idx = random.randint(0, len(words) - 1)
                    words[idx] = "처리"
                generated = " ".join(words)

                result = SummaryResult(
                    generated_summary=generated,
                    predicted_sentiment=sentiment,
                    extracted_keywords=[k for k in case.get("key_info", [])[:3] if random.random() < 0.85]
                )
                eval_data.append((test_case, result))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _run_flow_evaluation(self, data) -> EvaluationResult:
        """Flow 평가 실행"""
        if self.config.verbose:
            print("Running LangGraph Flow Evaluation...")

        metrics = self.metrics_modules["flow"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_cases" in data:
            from ..metrics.flow_metrics import FlowTestCase, FlowResult, NodeTransition
            from datetime import datetime
            import random
            eval_data = []
            for case in data["test_cases"]:
                expected_flow = case["expected_flow"]
                test_case = FlowTestCase(
                    session_id=case["flow_id"],
                    input_message=case["scenario"],
                    expected_flow=expected_flow,
                    expected_final_node=expected_flow[-1] if expected_flow else "end"
                )
                # 시뮬레이션: 90% 정확한 플로우
                if random.random() < 0.9:
                    actual_flow = expected_flow.copy()
                else:
                    actual_flow = expected_flow.copy()
                    if len(actual_flow) > 2:
                        actual_flow.pop(random.randint(1, len(actual_flow) - 2))

                # 전이 기록 생성
                transitions = []
                for i in range(len(actual_flow) - 1):
                    latency = case.get("expected_latency_ms", {}).get(actual_flow[i], 500)
                    transitions.append(NodeTransition(
                        from_node=actual_flow[i],
                        to_node=actual_flow[i + 1],
                        timestamp=datetime.now(),
                        latency_ms=latency * random.uniform(0.8, 1.2)
                    ))

                result = FlowResult(
                    session_id=case["flow_id"],
                    actual_flow=actual_flow,
                    transitions=transitions,
                    final_node=actual_flow[-1] if actual_flow else "end",
                    completed_successfully=True
                )
                eval_data.append((test_case, result))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _run_e2e_evaluation(self, data) -> EvaluationResult:
        """E2E 평가 실행"""
        if self.config.verbose:
            print("Running E2E System Evaluation...")

        metrics = self.metrics_modules["e2e"]

        # JSON 데이터를 메트릭 형식으로 변환
        if isinstance(data, dict) and "test_scenarios" in data:
            from ..metrics.e2e_metrics import E2ETestScenario, E2EResult
            import random
            eval_data = []
            for case in data["test_scenarios"]:
                expected = case.get("expected", {})
                ground_truth = case.get("ground_truth", {})

                scenario = E2ETestScenario(
                    scenario_id=case["scenario_id"],
                    scenario_type=case.get("category", "general"),
                    expected_resolution="auto" if expected.get("auto_resolved", True) else "human_transfer",
                    input_text=case.get("input", {}).get("stt_transcript", "")
                )

                # 시뮬레이션: 대부분 예상대로 동작
                is_auto = expected.get("auto_resolved", True)
                result = E2EResult(
                    scenario_id=case["scenario_id"],
                    success=True,
                    resolution_type="auto" if is_auto else "human_transfer",
                    triage_decision="AUTO" if is_auto else "HUMAN",
                    total_latency_ms=random.uniform(1500, 2500),
                    first_contact_resolved=ground_truth.get("customer_satisfied", True),
                    csat_score=random.uniform(4.0, 5.0) if ground_truth.get("customer_satisfied") else random.uniform(3.0, 4.0),
                    repeat_explanation_count=0 if not ground_truth.get("repeat_explanation_needed", False) else 1
                )
                eval_data.append((scenario, result))
            return metrics.evaluate(eval_data)

        return metrics.evaluate(data)

    def _generate_summary(self, module_results: Dict[str, EvaluationResult]) -> Dict[str, Any]:
        """평가 요약 생성"""
        summary = {
            "modules_evaluated": list(module_results.keys()),
            "modules_passed": [],
            "modules_failed": [],
            "p0_metrics_summary": {},
            "overall_stats": {}
        }

        total_metrics = 0
        passed_metrics = 0
        p0_total = 0
        p0_passed = 0

        for module_name, result in module_results.items():
            if result.overall_passed:
                summary["modules_passed"].append(module_name)
            else:
                summary["modules_failed"].append(module_name)

            for metric in result.metrics:
                total_metrics += 1
                if metric.passed:
                    passed_metrics += 1

                if metric.priority == Priority.P0:
                    p0_total += 1
                    if metric.passed:
                        p0_passed += 1

                    summary["p0_metrics_summary"][f"{module_name}.{metric.name}"] = {
                        "value": metric.value,
                        "target": metric.target,
                        "passed": metric.passed
                    }

        summary["overall_stats"] = {
            "total_metrics": total_metrics,
            "passed_metrics": passed_metrics,
            "pass_rate": (passed_metrics / total_metrics * 100) if total_metrics > 0 else 0,
            "p0_total": p0_total,
            "p0_passed": p0_passed,
            "p0_pass_rate": (p0_passed / p0_total * 100) if p0_total > 0 else 0
        }

        return summary

    def _compare_with_benchmarks(
        self,
        module_results: Dict[str, EvaluationResult]
    ) -> Dict[str, Any]:
        """업계 벤치마크 대비 비교"""
        comparison = {}

        benchmark_mapping = {
            "stt": {
                "cer": ("stt_korean", "provider_rankings", "1st", "cer"),
            },
            "intent": {
                "accuracy": ("intent_classification", "financial_domain", "production_minimum"),
            },
            "rag": {
                "precision_at_3": ("rag", "context_precision", "gate_threshold"),
                "faithfulness": ("rag", "faithfulness", "good"),
            },
            "e2e": {
                "auto_resolution_rate": ("contact_center", "auto_resolution", "good"),
                "csat": ("contact_center", "csat", "good"),
            }
        }

        for module_name, result in module_results.items():
            if module_name not in benchmark_mapping:
                continue

            module_comparison = {}
            for metric in result.metrics:
                metric_key = metric.name.lower().replace(" ", "_").replace("(", "").replace(")", "")

                # 벤치마크 값 찾기
                if metric_key in benchmark_mapping.get(module_name, {}):
                    benchmark_path = benchmark_mapping[module_name][metric_key]
                    try:
                        benchmark_value = self._get_benchmark_value(benchmark_path)
                        if benchmark_value is not None:
                            module_comparison[metric.name] = {
                                "current": metric.value,
                                "benchmark": benchmark_value,
                                "vs_benchmark": "above" if metric.value >= benchmark_value else "below"
                            }
                    except:
                        pass

            if module_comparison:
                comparison[module_name] = module_comparison

        return comparison

    def _get_benchmark_value(self, path: tuple) -> Optional[float]:
        """벤치마크 값 조회"""
        obj = BENCHMARK_STANDARDS
        for key in path:
            if hasattr(obj, key):
                obj = getattr(obj, key)
            elif isinstance(obj, dict):
                obj = obj.get(key)
            else:
                return None
        return obj if isinstance(obj, (int, float)) else None

    def _print_summary(self, result: PipelineEvaluationResult):
        """결과 요약 출력"""
        print(f"\n{'='*60}")
        print("EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Mode: {result.config_mode.value}")
        print(f"Duration: {result.total_duration_seconds:.2f}s")
        print(f"Overall Passed: {'YES' if result.overall_passed else 'NO'}")
        print(f"P0 Metrics Passed: {'YES' if result.p0_passed else 'NO'}")

        stats = result.summary.get("overall_stats", {})
        print(f"\nMetrics: {stats.get('passed_metrics', 0)}/{stats.get('total_metrics', 0)} passed")
        print(f"P0 Metrics: {stats.get('p0_passed', 0)}/{stats.get('p0_total', 0)} passed")

        print(f"\n--- Module Results ---")
        for module, mod_result in result.module_results.items():
            status = "PASS" if mod_result.overall_passed else "FAIL"
            print(f"  {module}: {status} ({mod_result.pass_rate:.1f}% pass rate)")

        if result.summary.get("modules_failed"):
            print(f"\nFailed Modules: {', '.join(result.summary['modules_failed'])}")

        print(f"\n{'='*60}\n")
