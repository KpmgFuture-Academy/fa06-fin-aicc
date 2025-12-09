"""
Module Evaluation Runner
========================

개별 모듈 평가 실행기
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Type
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ..configs.config import EvaluationConfig
from ..metrics.base import BaseMetrics, EvaluationResult
from ..metrics.stt_metrics import STTMetrics
from ..metrics.intent_metrics import IntentMetrics
from ..metrics.rag_metrics import RAGMetrics
from ..metrics.slot_metrics import SlotFillingMetrics
from ..metrics.summary_metrics import SummaryMetrics
from ..metrics.flow_metrics import FlowMetrics
from ..metrics.e2e_metrics import E2EMetrics


class ModuleEvaluationRunner:
    """개별 모듈 평가 실행기"""

    METRICS_CLASSES: Dict[str, Type[BaseMetrics]] = {
        "stt": STTMetrics,
        "intent": IntentMetrics,
        "rag": RAGMetrics,
        "slot_filling": SlotFillingMetrics,
        "summary": SummaryMetrics,
        "flow": FlowMetrics,
        "e2e": E2EMetrics
    }

    def __init__(self, module_name: str, config: Optional[EvaluationConfig] = None):
        """
        Args:
            module_name: 평가할 모듈 이름
            config: 평가 설정
        """
        if module_name not in self.METRICS_CLASSES:
            raise ValueError(f"Unknown module: {module_name}. Available: {list(self.METRICS_CLASSES.keys())}")

        self.module_name = module_name
        self.config = config or EvaluationConfig.for_module(module_name)
        self.metrics = self.METRICS_CLASSES[module_name]()

    def run(self, test_data: Any) -> EvaluationResult:
        """
        모듈 평가 실행

        Args:
            test_data: 테스트 데이터

        Returns:
            EvaluationResult: 평가 결과
        """
        print(f"\nRunning {self.module_name} Evaluation...")
        result = self.metrics.evaluate(test_data)

        self._print_result(result)
        return result

    def run_from_file(self, file_path: str) -> EvaluationResult:
        """
        파일에서 테스트 데이터 로드 후 평가 실행

        Args:
            file_path: 테스트 데이터 파일 경로
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)

        return self.run(test_data)

    def _print_result(self, result: EvaluationResult):
        """결과 출력"""
        print(f"\n--- {self.module_name} Evaluation Results ---")
        print(f"Passed: {'YES' if result.overall_passed else 'NO'}")
        print(f"P0 Passed: {'YES' if result.p0_passed else 'NO'}")
        print(f"Duration: {result.duration_seconds:.2f}s")

        print(f"\nMetrics ({len(result.metrics)} total):")
        for metric in result.metrics:
            status = "PASS" if metric.passed else "FAIL"
            print(f"  [{metric.priority.value}] {metric.name}: {metric.value:.2f}{metric.unit} "
                  f"(target: {metric.target}{metric.unit}) - {status}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                print(f"  - {error}")


def run_stt_evaluation(test_data: Any) -> EvaluationResult:
    """STT 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("stt")
    return runner.run(test_data)


def run_intent_evaluation(test_data: Any) -> EvaluationResult:
    """Intent 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("intent")
    return runner.run(test_data)


def run_rag_evaluation(test_data: Any) -> EvaluationResult:
    """RAG 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("rag")
    return runner.run(test_data)


def run_slot_evaluation(test_data: Any) -> EvaluationResult:
    """Slot Filling 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("slot_filling")
    return runner.run(test_data)


def run_summary_evaluation(test_data: Any) -> EvaluationResult:
    """Summary 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("summary")
    return runner.run(test_data)


def run_flow_evaluation(test_data: Any) -> EvaluationResult:
    """Flow 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("flow")
    return runner.run(test_data)


def run_e2e_evaluation(test_data: Any) -> EvaluationResult:
    """E2E 평가 헬퍼 함수"""
    runner = ModuleEvaluationRunner("e2e")
    return runner.run(test_data)
