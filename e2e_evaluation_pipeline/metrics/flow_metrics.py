"""
LangGraph Flow Metrics Evaluation
=================================

LangGraph 워크플로우 상태 전이 성능 평가

평가 지표:
    - Node Transition Accuracy: 노드 전이 정확도
    - Fallback Rate: 예외 처리 발생 비율
    - Infinite Loop Rate: 무한 루프 발생 비율
    - Session Completion Rate: 세션 정상 완료율
    - Average Node Visits: 평균 노드 방문 횟수
    - Node Latency: 노드별 처리 시간
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter

from .base import BaseMetrics, EvaluationResult
from ..configs.kpi_thresholds import DEFAULT_KPI_THRESHOLDS


@dataclass
class NodeTransition:
    """노드 전이 기록"""
    from_node: str
    to_node: str
    timestamp: datetime
    latency_ms: float
    state_snapshot: Optional[Dict[str, Any]] = None


@dataclass
class FlowTestCase:
    """Flow 테스트 케이스"""
    session_id: str
    input_message: str
    expected_flow: List[str]  # 예상 노드 방문 순서
    expected_final_node: str


@dataclass
class FlowResult:
    """Flow 실행 결과"""
    session_id: str
    actual_flow: List[str]  # 실제 노드 방문 순서
    transitions: List[NodeTransition]  # 전이 기록
    final_node: str
    completed_successfully: bool
    error_message: Optional[str] = None
    fallback_triggered: bool = False


class FlowMetrics(BaseMetrics):
    """LangGraph Flow 성능 평가 메트릭"""

    # 노드 목록
    NODES = [
        "triage_agent",
        "answer_agent",
        "consent_check_node",
        "waiting_agent",
        "chat_db_storage_node",
        "summary_agent",
        "human_transfer"
    ]

    # 유효한 전이 (from -> [to, ...])
    VALID_TRANSITIONS = {
        "__start__": ["triage_agent", "consent_check_node", "waiting_agent"],
        "triage_agent": ["answer_agent"],
        "answer_agent": ["chat_db_storage_node"],
        "consent_check_node": ["waiting_agent", "triage_agent"],
        "waiting_agent": ["chat_db_storage_node", "summary_agent"],
        "chat_db_storage_node": ["__end__", "summary_agent"],
        "summary_agent": ["human_transfer"],
        "human_transfer": ["__end__"]
    }

    def __init__(self):
        super().__init__(DEFAULT_KPI_THRESHOLDS.flow)
        self._max_visits_threshold = 20  # 무한 루프 감지 임계값

    @property
    def module_name(self) -> str:
        return "LangGraph Flow"

    def evaluate(self, data: List[Tuple[FlowTestCase, FlowResult]]) -> EvaluationResult:
        """
        Flow 성능 평가 실행

        Args:
            data: [(테스트케이스, 결과), ...] 리스트
        """
        self.reset()
        start_time = datetime.now()

        if not data:
            self.errors.append("No test data provided")
            return self._create_evaluation_result(start_time, {"error": "No data"})

        # 메트릭 계산
        transition_accuracies = []
        fallback_flags = []
        infinite_loop_flags = []
        completion_flags = []
        node_visit_counts = []

        # 노드별 latency 수집
        node_latencies = defaultdict(list)

        for test_case, result in data:
            try:
                # Transition Accuracy
                accuracy = self._calculate_transition_accuracy(
                    test_case.expected_flow,
                    result.actual_flow
                )
                transition_accuracies.append(accuracy)

                # Fallback Detection
                fallback_flags.append(1 if result.fallback_triggered else 0)

                # Infinite Loop Detection
                has_loop = self._detect_infinite_loop(result.actual_flow)
                infinite_loop_flags.append(1 if has_loop else 0)

                # Completion Status
                completion_flags.append(1 if result.completed_successfully else 0)

                # Node Visit Count
                node_visit_counts.append(len(result.actual_flow))

                # Node Latencies
                for transition in result.transitions:
                    if transition.from_node in self.NODES:
                        node_latencies[transition.from_node].append(transition.latency_ms)

            except Exception as e:
                self.errors.append(f"Error processing session {test_case.session_id}: {str(e)}")

        # 결과 집계
        summary = {
            "total_samples": len(data),
            "processed_samples": len(transition_accuracies)
        }

        # Transition Accuracy
        if transition_accuracies:
            avg_accuracy = sum(transition_accuracies) / len(transition_accuracies)
            self.results.append(self._create_metric_result(
                "transition_accuracy", avg_accuracy,
                details={
                    "perfect_matches": sum(1 for a in transition_accuracies if a == 100),
                    "partial_matches": sum(1 for a in transition_accuracies if 0 < a < 100)
                }
            ))
            summary["avg_transition_accuracy"] = avg_accuracy

        # Fallback Rate
        if fallback_flags:
            fallback_rate = (sum(fallback_flags) / len(fallback_flags)) * 100
            self.results.append(self._create_metric_result(
                "fallback_rate", fallback_rate
            ))
            summary["fallback_rate"] = fallback_rate

        # Infinite Loop Rate
        if infinite_loop_flags:
            loop_rate = (sum(infinite_loop_flags) / len(infinite_loop_flags)) * 100
            self.results.append(self._create_metric_result(
                "infinite_loop_rate", loop_rate
            ))
            summary["infinite_loop_rate"] = loop_rate

        # Session Completion Rate
        if completion_flags:
            completion_rate = (sum(completion_flags) / len(completion_flags)) * 100
            self.results.append(self._create_metric_result(
                "session_completion_rate", completion_rate
            ))
            summary["session_completion_rate"] = completion_rate

        # Average Node Visits
        if node_visit_counts:
            avg_visits = sum(node_visit_counts) / len(node_visit_counts)
            self.results.append(self._create_metric_result(
                "avg_node_visits", avg_visits,
                details={
                    "min": min(node_visit_counts),
                    "max": max(node_visit_counts)
                }
            ))
            summary["avg_node_visits"] = avg_visits

        # Node Latencies
        latency_summary = {}
        for node_name, latencies in node_latencies.items():
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                metric_key = f"latency_{node_name}"

                if metric_key in self.kpi_metrics:
                    self.results.append(self._create_metric_result(
                        metric_key, avg_latency,
                        details={
                            "min": min(latencies),
                            "max": max(latencies),
                            "p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
                        }
                    ))
                latency_summary[node_name] = avg_latency

        summary["node_latencies"] = latency_summary

        return self._create_evaluation_result(start_time, summary)

    def _calculate_transition_accuracy(
        self,
        expected_flow: List[str],
        actual_flow: List[str]
    ) -> float:
        """노드 전이 정확도 계산"""
        if not expected_flow:
            return 100.0 if not actual_flow else 0.0

        if not actual_flow:
            return 0.0

        # 순서를 고려한 매칭 (LCS 기반)
        lcs_length = self._lcs_length(expected_flow, actual_flow)

        # 정확도 계산 (예상 대비)
        return (lcs_length / len(expected_flow)) * 100

    def _lcs_length(self, x: List[str], y: List[str]) -> int:
        """최장 공통 부분 수열 길이"""
        m, n = len(x), len(y)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if x[i-1] == y[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        return dp[m][n]

    def _detect_infinite_loop(self, flow: List[str]) -> bool:
        """무한 루프 감지"""
        if len(flow) > self._max_visits_threshold:
            return True

        # 동일 노드 연속 방문 패턴 감지
        for i in range(len(flow) - 2):
            pattern = flow[i:i+2]
            count = 0
            for j in range(i, len(flow) - 1):
                if flow[j:j+2] == pattern:
                    count += 1
            if count >= 5:  # 같은 패턴 5회 이상 반복
                return True

        # 특정 노드 과다 방문
        node_counts = Counter(flow)
        for node, count in node_counts.items():
            if count >= 10:  # 단일 노드 10회 이상 방문
                return True

        return False

    def validate_flow(self, flow: List[str]) -> Tuple[bool, List[str]]:
        """
        플로우 유효성 검증

        Returns:
            (is_valid, list of invalid transitions)
        """
        invalid_transitions = []

        for i in range(len(flow) - 1):
            from_node = flow[i]
            to_node = flow[i + 1]

            valid_targets = self.VALID_TRANSITIONS.get(from_node, [])
            if to_node not in valid_targets:
                invalid_transitions.append(f"{from_node} -> {to_node}")

        return len(invalid_transitions) == 0, invalid_transitions

    def get_flow_statistics(
        self,
        results: List[FlowResult]
    ) -> Dict[str, Any]:
        """플로우 통계 분석"""
        all_flows = [r.actual_flow for r in results]

        # 노드별 방문 빈도
        node_frequencies = Counter()
        for flow in all_flows:
            node_frequencies.update(flow)

        # 전이 빈도
        transition_frequencies = Counter()
        for flow in all_flows:
            for i in range(len(flow) - 1):
                transition = f"{flow[i]} -> {flow[i+1]}"
                transition_frequencies[transition] += 1

        # 평균 플로우 길이
        avg_length = sum(len(f) for f in all_flows) / len(all_flows) if all_flows else 0

        # 종료 노드 분포
        final_nodes = Counter(r.final_node for r in results)

        return {
            "node_frequencies": dict(node_frequencies),
            "top_transitions": dict(transition_frequencies.most_common(10)),
            "avg_flow_length": avg_length,
            "final_node_distribution": dict(final_nodes)
        }


def trace_langgraph_execution(
    workflow,
    input_state: Dict[str, Any]
) -> FlowResult:
    """
    LangGraph 워크플로우 실행 추적

    Args:
        workflow: 컴파일된 LangGraph 워크플로우
        input_state: 입력 상태
    """
    import time

    session_id = input_state.get("session_id", "unknown")
    actual_flow = []
    transitions = []
    error_message = None
    fallback_triggered = False

    try:
        # 워크플로우 스트리밍 실행으로 각 노드 추적
        prev_node = "__start__"
        prev_time = time.time()

        for event in workflow.stream(input_state):
            current_node = list(event.keys())[0] if event else None
            current_time = time.time()

            if current_node:
                actual_flow.append(current_node)

                transition = NodeTransition(
                    from_node=prev_node,
                    to_node=current_node,
                    timestamp=datetime.now(),
                    latency_ms=(current_time - prev_time) * 1000,
                    state_snapshot=event.get(current_node)
                )
                transitions.append(transition)

                prev_node = current_node
                prev_time = current_time

        completed = True
        final_node = actual_flow[-1] if actual_flow else "__end__"

    except Exception as e:
        error_message = str(e)
        completed = False
        final_node = actual_flow[-1] if actual_flow else "__error__"
        fallback_triggered = True

    return FlowResult(
        session_id=session_id,
        actual_flow=actual_flow,
        transitions=transitions,
        final_node=final_node,
        completed_successfully=completed,
        error_message=error_message,
        fallback_triggered=fallback_triggered
    )
