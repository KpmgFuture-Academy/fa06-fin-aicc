"""
E2E (End-to-End) System Metrics Evaluation
==========================================

전체 시스템 통합 성능 평가

평가 지표:
    - Auto Resolution Rate: AI 자동 해결률
    - E2E Latency: 음성→응답 전체 응답 시간
    - Repeat Explanation Reduction: 반복 설명 감소율
    - AHT Reduction: 상담사 처리 시간 감소율
    - Transfer Failure Rate: 상담사 연결 실패율
    - CSAT: 고객 만족도
    - FCR: 첫 응대 해결률
    - System Availability: 시스템 가용성
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class E2ETestScenario:
    """E2E 테스트 시나리오"""
    scenario_id: str
    scenario_type: str  # "auto_resolve", "human_transfer", "slot_filling", etc.
    expected_resolution: str  # "auto", "human_transfer"
    input_audio_path: Optional[str] = None
    input_text: Optional[str] = None
    expected_intent: Optional[str] = None

    # 비교용 베이스라인
    baseline_aht_seconds: Optional[float] = None  # 기존 상담사 처리 시간
    baseline_repeat_count: Optional[int] = None   # 기존 반복 설명 횟수


@dataclass
class E2EResult:
    """E2E 실행 결과"""
    scenario_id: str
    success: bool

    # 해결 정보
    resolution_type: str  # "auto", "human_transfer", "failed"
    triage_decision: str

    # 타이밍
    total_latency_ms: float
    stt_latency_ms: Optional[float] = None
    llm_latency_ms: Optional[float] = None
    tts_latency_ms: Optional[float] = None

    # 상담 품질
    actual_aht_seconds: Optional[float] = None
    repeat_explanation_count: int = 0
    customer_satisfied: Optional[bool] = None
    csat_score: Optional[float] = None
    first_contact_resolved: bool = False

    # 에러 정보
    error_message: Optional[str] = None
    transfer_failed: bool = False


class E2EMetrics(BaseMetrics):
    """E2E 시스템 성능 평가 메트릭"""

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.e2e)

    @property
    def module_name(self) -> str:
        return "E2E System"

    def evaluate(self, data: List[Tuple[E2ETestScenario, E2EResult]]) -> EvaluationResult:
        """
        E2E 시스템 성능 평가 실행

        Args:
            data: [(시나리오, 결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산 데이터 수집
        auto_resolutions = []
        latencies = []
        aht_improvements = []
        repeat_reductions = []
        transfer_failures = []
        csat_scores = []
        fcr_flags = []

        for scenario, result in data:
            try:
                # Auto Resolution (자동 해결 여부)
                if scenario.expected_resolution == "auto":
                    auto_resolutions.append(1 if result.resolution_type == "auto" else 0)
                elif result.resolution_type == "auto":
                    auto_resolutions.append(1)
                else:
                    auto_resolutions.append(0)

                # E2E Latency
                latencies.append(result.total_latency_ms)

                # AHT Improvement (베이스라인 대비)
                if scenario.baseline_aht_seconds and result.actual_aht_seconds:
                    improvement = ((scenario.baseline_aht_seconds - result.actual_aht_seconds)
                                  / scenario.baseline_aht_seconds * 100)
                    aht_improvements.append(improvement)

                # Repeat Explanation Reduction
                if scenario.baseline_repeat_count is not None:
                    if scenario.baseline_repeat_count > 0:
                        reduction = ((scenario.baseline_repeat_count - result.repeat_explanation_count)
                                    / scenario.baseline_repeat_count * 100)
                        repeat_reductions.append(max(0, reduction))
                    else:
                        repeat_reductions.append(100.0 if result.repeat_explanation_count == 0 else 0.0)

                # Transfer Failure
                transfer_failures.append(1 if result.transfer_failed else 0)

                # CSAT
                if result.csat_score is not None:
                    csat_scores.append(result.csat_score)

                # FCR
                fcr_flags.append(1 if result.first_contact_resolved else 0)

            except Exception as e:
                self.errors.append(f"Error processing scenario {scenario.scenario_id}: {str(e)}")

        # 결과 집계
        summary = {
            "total_scenarios": len(data),
            "processed_scenarios": len(latencies)
        }

        # Auto Resolution Rate
        if auto_resolutions:
            auto_rate = (sum(auto_resolutions) / len(auto_resolutions)) * 100
            self.results.append(self._create_metric_result(
                "auto_resolution_rate", auto_rate,
                details={
                    "auto_resolved": sum(auto_resolutions),
                    "total": len(auto_resolutions)
                }
            ))
            summary["auto_resolution_rate"] = auto_rate

        # E2E Latency
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            self.results.append(self._create_metric_result(
                "e2e_latency", avg_latency,
                details={
                    "min": min(latencies),
                    "max": max(latencies),
                    "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
                    "under_1s": sum(1 for l in latencies if l < 1000),
                    "under_3s": sum(1 for l in latencies if l < 3000)
                }
            ))
            summary["avg_e2e_latency_ms"] = avg_latency

        # Repeat Explanation Reduction
        if repeat_reductions:
            avg_reduction = sum(repeat_reductions) / len(repeat_reductions)
            self.results.append(self._create_metric_result(
                "repeat_explanation_reduction", avg_reduction
            ))
            summary["repeat_explanation_reduction"] = avg_reduction

        # AHT Reduction
        if aht_improvements:
            avg_aht_improvement = sum(aht_improvements) / len(aht_improvements)
            self.results.append(self._create_metric_result(
                "aht_reduction", avg_aht_improvement
            ))
            summary["aht_reduction"] = avg_aht_improvement

        # Transfer Failure Rate
        if transfer_failures:
            failure_rate = (sum(transfer_failures) / len(transfer_failures)) * 100
            self.results.append(self._create_metric_result(
                "transfer_failure_rate", failure_rate
            ))
            summary["transfer_failure_rate"] = failure_rate

        # CSAT
        if csat_scores:
            avg_csat = sum(csat_scores) / len(csat_scores)
            # 5점 만점을 100점 만점으로 변환
            csat_percentage = (avg_csat / 5) * 100 if avg_csat <= 5 else avg_csat
            self.results.append(self._create_metric_result(
                "csat", csat_percentage,
                details={
                    "avg_score": avg_csat,
                    "responses": len(csat_scores)
                }
            ))
            summary["avg_csat"] = avg_csat

        # FCR
        if fcr_flags:
            fcr_rate = (sum(fcr_flags) / len(fcr_flags)) * 100
            self.results.append(self._create_metric_result(
                "fcr", fcr_rate
            ))
            summary["fcr_rate"] = fcr_rate

        return self._create_evaluation_result(start_time, summary)

    def evaluate_by_scenario_type(
        self,
        data: List[Tuple[E2ETestScenario, E2EResult]]
    ) -> Dict[str, EvaluationResult]:
        """시나리오 유형별 평가"""
        # 유형별 데이터 분류
        by_type = defaultdict(list)
        for scenario, result in data:
            by_type[scenario.scenario_type].append((scenario, result))

        # 유형별 평가 실행
        results = {}
        for scenario_type, type_data in by_type.items():
            results[scenario_type] = self.evaluate(type_data)

        return results

    def compare_with_baseline(
        self,
        current_results: EvaluationResult,
        baseline_results: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """베이스라인 대비 비교"""
        comparison = {}

        for metric in current_results.metrics:
            baseline_value = baseline_results.get(metric.name)
            if baseline_value is not None:
                if metric.passed:  # higher_is_better가 True인 경우
                    improvement = ((metric.value - baseline_value) / baseline_value * 100
                                  if baseline_value != 0 else 0)
                else:
                    improvement = ((baseline_value - metric.value) / baseline_value * 100
                                  if baseline_value != 0 else 0)

                comparison[metric.name] = {
                    "current": metric.value,
                    "baseline": baseline_value,
                    "improvement_pct": improvement,
                    "improved": improvement > 0
                }

        return comparison


@dataclass
class SystemHealthCheck:
    """시스템 상태 점검 결과"""
    timestamp: datetime
    is_healthy: bool
    response_time_ms: float
    components: Dict[str, bool]
    error_messages: List[str] = field(default_factory=list)


def check_system_availability(
    health_checks: List[SystemHealthCheck],
    time_window_hours: int = 24
) -> Dict[str, Any]:
    """
    시스템 가용성 계산

    Args:
        health_checks: 상태 점검 결과 리스트
        time_window_hours: 분석 기간 (시간)
    """
    if not health_checks:
        return {"availability": 0.0, "error": "No health check data"}

    # 시간 범위 필터
    cutoff = datetime.now() - timedelta(hours=time_window_hours)
    recent_checks = [c for c in health_checks if c.timestamp > cutoff]

    if not recent_checks:
        return {"availability": 0.0, "error": "No recent health checks"}

    # 가용성 계산
    healthy_count = sum(1 for c in recent_checks if c.is_healthy)
    availability = (healthy_count / len(recent_checks)) * 100

    # 컴포넌트별 가용성
    component_health = defaultdict(lambda: {"healthy": 0, "total": 0})
    for check in recent_checks:
        for component, is_healthy in check.components.items():
            component_health[component]["total"] += 1
            if is_healthy:
                component_health[component]["healthy"] += 1

    component_availability = {
        comp: (data["healthy"] / data["total"] * 100) if data["total"] > 0 else 0
        for comp, data in component_health.items()
    }

    # 평균 응답 시간
    avg_response_time = sum(c.response_time_ms for c in recent_checks) / len(recent_checks)

    return {
        "availability": availability,
        "total_checks": len(recent_checks),
        "healthy_checks": healthy_count,
        "avg_response_time_ms": avg_response_time,
        "component_availability": component_availability,
        "time_window_hours": time_window_hours
    }


def run_e2e_test(
    workflow,
    stt_service,
    tts_service,
    scenario: E2ETestScenario
) -> E2EResult:
    """
    E2E 테스트 실행

    Args:
        workflow: LangGraph 워크플로우
        stt_service: STT 서비스
        tts_service: TTS 서비스
        scenario: 테스트 시나리오
    """
    import time

    start_time = time.time()
    stt_latency = None
    llm_latency = None
    tts_latency = None
    error_message = None

    try:
        # 1. STT (음성 입력인 경우)
        if scenario.input_audio_path:
            stt_start = time.time()
            stt_result = stt_service.transcribe_file(scenario.input_audio_path)
            stt_latency = (time.time() - stt_start) * 1000
            input_text = stt_result.text
        else:
            input_text = scenario.input_text or ""

        # 2. LangGraph 워크플로우 실행
        llm_start = time.time()
        state = {
            "session_id": scenario.scenario_id,
            "user_message": input_text,
            "conversation_history": []
        }

        result_state = workflow.invoke(state)
        llm_latency = (time.time() - llm_start) * 1000

        # 3. TTS (필요한 경우)
        ai_message = result_state.get("ai_message", "")
        if ai_message and tts_service:
            tts_start = time.time()
            tts_service.synthesize(ai_message)
            tts_latency = (time.time() - tts_start) * 1000

        total_latency = (time.time() - start_time) * 1000

        # 결과 분석
        triage_decision = result_state.get("triage_decision", "UNKNOWN")
        is_human_required = result_state.get("is_human_required_flow", False)

        resolution_type = "human_transfer" if is_human_required else "auto"
        success = True
        transfer_failed = False

    except Exception as e:
        error_message = str(e)
        success = False
        resolution_type = "failed"
        triage_decision = "ERROR"
        transfer_failed = True
        total_latency = (time.time() - start_time) * 1000

    return E2EResult(
        scenario_id=scenario.scenario_id,
        success=success,
        resolution_type=resolution_type,
        triage_decision=triage_decision,
        total_latency_ms=total_latency,
        stt_latency_ms=stt_latency,
        llm_latency_ms=llm_latency,
        tts_latency_ms=tts_latency,
        error_message=error_message,
        transfer_failed=transfer_failed
    )
