"""
Base classes for metrics evaluation
===================================

모든 메트릭 클래스의 기본 클래스
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
import json

from ..configs.kpi_thresholds import KPIMetric, EvaluationLevel, Priority


@dataclass
class MetricResult:
    """개별 메트릭 결과"""
    name: str
    value: float
    unit: str
    target: float
    level: EvaluationLevel
    priority: Priority
    passed: bool
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "target": self.target,
            "level": self.level.value,
            "priority": self.priority.value,
            "passed": self.passed,
            "details": self.details
        }


@dataclass
class EvaluationResult:
    """전체 평가 결과"""
    module_name: str
    timestamp: datetime
    metrics: List[MetricResult]
    overall_passed: bool
    summary: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def p0_passed(self) -> bool:
        """P0 메트릭 모두 통과 여부"""
        p0_metrics = [m for m in self.metrics if m.priority == Priority.P0]
        return all(m.passed for m in p0_metrics)

    @property
    def pass_rate(self) -> float:
        """전체 통과율"""
        if not self.metrics:
            return 0.0
        return sum(1 for m in self.metrics if m.passed) / len(self.metrics) * 100

    @property
    def p0_pass_rate(self) -> float:
        """P0 메트릭 통과율"""
        p0_metrics = [m for m in self.metrics if m.priority == Priority.P0]
        if not p0_metrics:
            return 100.0
        return sum(1 for m in p0_metrics if m.passed) / len(p0_metrics) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "timestamp": self.timestamp.isoformat(),
            "metrics": [m.to_dict() for m in self.metrics],
            "overall_passed": self.overall_passed,
            "p0_passed": self.p0_passed,
            "pass_rate": self.pass_rate,
            "p0_pass_rate": self.p0_pass_rate,
            "summary": self.summary,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class BaseMetrics(ABC):
    """메트릭 평가 기본 클래스"""

    def __init__(self, kpi_metrics: Dict[str, KPIMetric]):
        """
        Args:
            kpi_metrics: KPI 메트릭 정의 (kpi_thresholds에서 가져옴)
        """
        self.kpi_metrics = kpi_metrics
        self.results: List[MetricResult] = []
        self.errors: List[str] = []

    @property
    @abstractmethod
    def module_name(self) -> str:
        """모듈 이름"""
        pass

    @abstractmethod
    def evaluate(self, data: Any) -> EvaluationResult:
        """
        평가 실행

        Args:
            data: 평가할 데이터

        Returns:
            EvaluationResult: 평가 결과
        """
        pass

    def _create_metric_result(
        self,
        metric_key: str,
        actual_value: float,
        details: Optional[Dict[str, Any]] = None
    ) -> MetricResult:
        """
        메트릭 결과 생성

        Args:
            metric_key: KPI 메트릭 키
            actual_value: 실제 측정값
            details: 상세 정보
        """
        kpi = self.kpi_metrics.get(metric_key)
        if not kpi:
            raise ValueError(f"Unknown metric key: {metric_key}")

        level = kpi.evaluate(actual_value)

        # 통과 여부 판단
        if kpi.higher_is_better:
            passed = actual_value >= kpi.target
        else:
            passed = actual_value <= kpi.target

        return MetricResult(
            name=kpi.name,
            value=actual_value,
            unit=kpi.unit,
            target=kpi.target,
            level=level,
            priority=kpi.priority,
            passed=passed,
            details=details
        )

    def _create_evaluation_result(
        self,
        start_time: datetime,
        summary: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """평가 결과 생성"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # P0 메트릭 기준으로 overall_passed 판단
        p0_metrics = [m for m in self.results if m.priority == Priority.P0]
        overall_passed = all(m.passed for m in p0_metrics) if p0_metrics else True

        return EvaluationResult(
            module_name=self.module_name,
            timestamp=end_time,
            metrics=self.results,
            overall_passed=overall_passed,
            summary=summary or {},
            errors=self.errors,
            duration_seconds=duration
        )

    def reset(self):
        """결과 초기화"""
        self.results = []
        self.errors = []
