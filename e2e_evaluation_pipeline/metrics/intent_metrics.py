"""
Intent Classification Metrics Evaluation
=========================================

KcELECTRA + LoRA 의도 분류 모델 성능 평가

평가 지표:
    - Accuracy: 전체 정확도
    - Weighted F1: 가중 F1 점수
    - Macro F1: 매크로 F1 점수
    - HUMAN_REQUIRED Recall: 상담사 연결 필요 케이스 탐지율
    - Top-3 Accuracy: 상위 3개 예측 중 정답 포함률
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class IntentTestCase:
    """Intent 테스트 케이스"""
    text: str
    true_label: str
    domain: Optional[str] = None


@dataclass
class IntentPrediction:
    """Intent 예측 결과"""
    predicted_label: str
    confidence: float
    top_k_predictions: List[Tuple[str, float]]  # [(label, confidence), ...]


class IntentMetrics(BaseMetrics):
    """Intent 분류 성능 평가 메트릭"""

    # HUMAN_REQUIRED 관련 레이블들
    HUMAN_REQUIRED_LABELS = [
        "상담사 연결",
        "상담원 연결",
        "직원 연결",
        "HUMAN_REQUIRED"
    ]

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.intent)
        self._label_mapping: Dict[str, int] = {}

    @property
    def module_name(self) -> str:
        return "Intent Classification"

    def set_label_mapping(self, labels: List[str]):
        """레이블 매핑 설정"""
        self._label_mapping = {label: idx for idx, label in enumerate(labels)}

    def evaluate(self, data: List[Tuple[IntentTestCase, IntentPrediction]]) -> EvaluationResult:
        """
        Intent 분류 성능 평가 실행

        Args:
            data: [(테스트케이스, 예측결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 데이터 추출
        y_true = [tc.true_label for tc, _ in data]
        y_pred = [pred.predicted_label for _, pred in data]
        top_k_preds = [pred.top_k_predictions for _, pred in data]

        # 메트릭 계산
        try:
            # Accuracy
            accuracy = self._calculate_accuracy(y_true, y_pred)
            self.results.append(self._create_metric_result(
                "accuracy", accuracy,
                details={"correct": sum(1 for t, p in zip(y_true, y_pred) if t == p), "total": len(y_true)}
            ))

            # Weighted F1
            weighted_f1 = self._calculate_weighted_f1(y_true, y_pred)
            self.results.append(self._create_metric_result(
                "weighted_f1", weighted_f1
            ))

            # Macro F1
            macro_f1 = self._calculate_macro_f1(y_true, y_pred)
            self.results.append(self._create_metric_result(
                "macro_f1", macro_f1
            ))

            # HUMAN_REQUIRED Recall
            human_recall = self._calculate_human_required_recall(y_true, y_pred)
            self.results.append(self._create_metric_result(
                "human_required_recall", human_recall,
                details=self._get_human_required_details(y_true, y_pred)
            ))

            # Top-3 Accuracy
            top3_accuracy = self._calculate_top_k_accuracy(y_true, top_k_preds, k=3)
            self.results.append(self._create_metric_result(
                "top3_accuracy", top3_accuracy
            ))

        except Exception as e:
            self.errors.append(f"Error calculating metrics: {str(e)}")

        # 요약 정보
        summary = {
            "total_samples": len(data),
            "unique_labels": len(set(y_true)),
            "accuracy": accuracy if 'accuracy' in dir() else None,
            "class_distribution": self._get_class_distribution(y_true)
        }

        return self._create_evaluation_result(start_time, summary)

    def _calculate_accuracy(self, y_true: List[str], y_pred: List[str]) -> float:
        """정확도 계산"""
        if not y_true:
            return 0.0
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        return (correct / len(y_true)) * 100

    def _calculate_weighted_f1(self, y_true: List[str], y_pred: List[str]) -> float:
        """가중 F1 점수 계산"""
        labels = list(set(y_true) | set(y_pred))
        f1_scores = []
        weights = []

        for label in labels:
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            support = sum(1 for t in y_true if t == label)
            f1_scores.append(f1)
            weights.append(support)

        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        weighted_f1 = sum(f * w for f, w in zip(f1_scores, weights)) / total_weight
        return weighted_f1 * 100

    def _calculate_macro_f1(self, y_true: List[str], y_pred: List[str]) -> float:
        """매크로 F1 점수 계산"""
        labels = list(set(y_true) | set(y_pred))
        f1_scores = []

        for label in labels:
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            f1_scores.append(f1)

        if not f1_scores:
            return 0.0

        return (sum(f1_scores) / len(f1_scores)) * 100

    def _calculate_human_required_recall(self, y_true: List[str], y_pred: List[str]) -> float:
        """HUMAN_REQUIRED 레이블 Recall 계산"""
        # HUMAN_REQUIRED 관련 레이블 찾기
        human_labels = set()
        for label in set(y_true):
            if any(hr in label.upper() for hr in ["HUMAN", "상담사", "상담원", "직원"]):
                human_labels.add(label)

        if not human_labels:
            return 100.0  # HUMAN_REQUIRED 케이스가 없으면 100%

        # True Positives와 False Negatives 계산
        tp = sum(1 for t, p in zip(y_true, y_pred) if t in human_labels and p in human_labels)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t in human_labels and p not in human_labels)

        if tp + fn == 0:
            return 100.0

        return (tp / (tp + fn)) * 100

    def _get_human_required_details(self, y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
        """HUMAN_REQUIRED 관련 상세 정보"""
        human_labels = set()
        for label in set(y_true):
            if any(hr in label.upper() for hr in ["HUMAN", "상담사", "상담원", "직원"]):
                human_labels.add(label)

        tp = sum(1 for t, p in zip(y_true, y_pred) if t in human_labels and p in human_labels)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t not in human_labels and p in human_labels)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t in human_labels and p not in human_labels)
        tn = sum(1 for t, p in zip(y_true, y_pred) if t not in human_labels and p not in human_labels)

        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "precision": (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0,
            "recall": (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0,
            "human_labels": list(human_labels)
        }

    def _calculate_top_k_accuracy(
        self,
        y_true: List[str],
        top_k_preds: List[List[Tuple[str, float]]],
        k: int = 3
    ) -> float:
        """Top-K 정확도 계산"""
        if not y_true:
            return 0.0

        correct = 0
        for true_label, preds in zip(y_true, top_k_preds):
            top_k_labels = [p[0] for p in preds[:k]]
            if true_label in top_k_labels:
                correct += 1

        return (correct / len(y_true)) * 100

    def _get_class_distribution(self, y_true: List[str]) -> Dict[str, int]:
        """클래스 분포"""
        distribution = defaultdict(int)
        for label in y_true:
            distribution[label] += 1
        return dict(distribution)

    def get_confusion_matrix(
        self,
        y_true: List[str],
        y_pred: List[str]
    ) -> Tuple[List[List[int]], List[str]]:
        """Confusion Matrix 생성"""
        labels = sorted(list(set(y_true) | set(y_pred)))
        label_to_idx = {label: idx for idx, label in enumerate(labels)}

        matrix = [[0] * len(labels) for _ in range(len(labels))]

        for true_label, pred_label in zip(y_true, y_pred):
            true_idx = label_to_idx[true_label]
            pred_idx = label_to_idx[pred_label]
            matrix[true_idx][pred_idx] += 1

        return matrix, labels

    def get_per_class_metrics(
        self,
        y_true: List[str],
        y_pred: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """클래스별 메트릭"""
        labels = list(set(y_true) | set(y_pred))
        result = {}

        for label in labels:
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            support = sum(1 for t in y_true if t == label)

            result[label] = {
                "precision": precision * 100,
                "recall": recall * 100,
                "f1": f1 * 100,
                "support": support
            }

        return result


def evaluate_intent_from_model(
    test_data_path: str,
    model_path: Optional[str] = None
) -> EvaluationResult:
    """
    모델 기반 Intent 평가 헬퍼 함수

    Args:
        test_data_path: 테스트 데이터 JSON 경로
        model_path: 모델 경로 (None이면 기본 경로)
    """
    import json
    import sys
    from pathlib import Path

    # 프로젝트 경로 추가
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from ai_engine.ingestion.bert_financial_intent_classifier.scripts.inference import IntentClassifier
    except ImportError:
        raise ImportError("Intent classifier module not found")

    # 모델 로드
    classifier = IntentClassifier(model_path)

    # 테스트 데이터 로드
    with open(test_data_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    # 평가 데이터 준비
    eval_data = []
    for item in test_data:
        test_case = IntentTestCase(
            text=item["text"],
            true_label=item["label"],
            domain=item.get("domain")
        )

        # 예측 실행
        predictions = classifier.predict(item["text"], top_k=3)
        top_pred = predictions[0] if predictions else {"intent": "unknown", "confidence": 0.0}

        prediction = IntentPrediction(
            predicted_label=top_pred["intent"],
            confidence=top_pred["confidence"],
            top_k_predictions=[(p["intent"], p["confidence"]) for p in predictions]
        )

        eval_data.append((test_case, prediction))

    # 평가 실행
    metrics = IntentMetrics()
    return metrics.evaluate(eval_data)
