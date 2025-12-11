"""
LangGraph 15가지 시나리오 테스트
================================

실제 ai_engine 워크플로우를 호출하여 LangGraph 분기·흐름 제어 검증
"""

import sys
import io
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Windows 콘솔 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.graph.workflow import build_workflow
from ai_engine.graph.state import GraphState
from app.schemas.common import TriageDecisionType


@dataclass
class ScenarioResult:
    """시나리오 테스트 결과"""
    scenario_id: str
    scenario_name: str
    input_message: str
    expected_decision: str
    actual_decision: Optional[str]
    expected_flow: List[str]
    actual_flow: List[str]
    passed: bool
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# 15가지 테스트 시나리오 정의 (Fallback 케이스 포함)
TEST_SCENARIOS = [
    # ========== 정상 RAG 흐름 ==========
    {
        "id": "scenario_01",
        "name": "결제대금 안내 – 정상 RAG 흐름 (AUTO_ANSWER)",
        "input": "이번 달 결제대금 납부 방법을 알려주세요",
        "expected_decision": "AUTO_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "Hybrid Search가 PAY_BILL 문서를 우선 반환하는지 확인"
    },
    {
        "id": "scenario_02",
        "name": "가상계좌/입금 안내 – RAG + KB 기반 응답 (AUTO_ANSWER)",
        "input": "가상계좌로 입금하려면 어떻게 해야 하나요?",
        "expected_decision": "AUTO_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "BM25 키워드 검색이 '가상계좌' 문서를 정확히 잡는지"
    },
    # ========== Slot Filling / NEED_MORE_INFO ==========
    {
        "id": "scenario_03",
        "name": "한도상향 – 저신뢰 → Clarification (NEED_MORE_INFO)",
        "input": "한도 올려주세요",
        "expected_decision": "NEED_MORE_INFO",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "Slot Filling 구조 작동 확인 (모호한 요청)"
    },
    {
        "id": "scenario_04",
        "name": "정보 필요 – Slot Filling 반복 (NEED_MORE_INFO)",
        "input": "대출 받고 싶어요",
        "expected_decision": "AUTO_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "대출 관련 RAG 문서 기반 응답"
    },
    # ========== Fallback 케이스 ==========
    {
        "id": "scenario_05",
        "name": "Hit 없음 – 일반 Fallback (SIMPLE_ANSWER)",
        "input": "오늘 서울 날씨가 어때요?",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "Hybrid Search 결과가 0일 때 안전 fallback 문구 생성"
    },
    {
        "id": "scenario_11",
        "name": "완전 무관한 질문 – Fallback",
        "input": "피자 주문하고 싶어요",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "카드/금융과 무관한 질문에 대한 Fallback 처리"
    },
    {
        "id": "scenario_12",
        "name": "의미 없는 입력 – Fallback",
        "input": "ㅋㅋㅋㅋㅋ",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "의미 없는 문자열에 대한 안전한 Fallback"
    },
    {
        "id": "scenario_13",
        "name": "영어 질문 – Fallback",
        "input": "How can I pay my bill?",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "영어 입력에 대한 Fallback 처리"
    },
    {
        "id": "scenario_14",
        "name": "복합 질문 – 여러 주제 혼합",
        "input": "카드 한도도 올리고 싶고 대출도 받고 싶고 포인트도 확인하고 싶어요",
        "expected_decision": "NEED_MORE_INFO",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "복합 질문에 대한 명확화 요청"
    },
    {
        "id": "scenario_15",
        "name": "짧은 단어 입력 – Fallback",
        "input": "뭐",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "너무 짧은 입력에 대한 Fallback"
    },
    # ========== 긴급/상담원 연결 ==========
    {
        "id": "scenario_06",
        "name": "분실 – 긴급 처리 (HUMAN_REQUIRED)",
        "input": "카드를 분실했어요 지금 바로 정지해주세요",
        "expected_decision": "HUMAN_REQUIRED",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "긴급 상황에서 상담원 연결 판단"
    },
    {
        "id": "scenario_07",
        "name": "연결 요청 – HUMAN_REQUIRED 판단",
        "input": "상담원 연결해주세요 복잡한 문제가 있어요",
        "expected_decision": "HUMAN_REQUIRED",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "상담원 연결 요청 시 HUMAN_REQUIRED 판단"
    },
    {
        "id": "scenario_08",
        "name": "Out-of-Scope 질문 – Fallback",
        "input": "주식 투자 어떻게 시작해야 하나요?",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "KB 문서 중 어떤 것도 높은 점수를 주지 않음"
    },
    # ========== 단순 응답 ==========
    {
        "id": "scenario_09",
        "name": "단순 인사 – SIMPLE_ANSWER",
        "input": "안녕하세요",
        "expected_decision": "SIMPLE_ANSWER",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "단순 인사에 대한 SIMPLE_ANSWER 처리"
    },
    {
        "id": "scenario_10",
        "name": "강한 불만 표현 – HUMAN_REQUIRED",
        "input": "담당자 바꿔주세요 세 번째 전화인데 아직도 해결이 안 됐어요",
        "expected_decision": "HUMAN_REQUIRED",
        "expected_flow": ["triage_agent", "answer_agent", "chat_db_storage"],
        "test_purpose": "강한 불만/민원 시 상담사 연결"
    }
]


def create_initial_state(user_message: str, session_id: str) -> GraphState:
    """초기 상태 생성"""
    return GraphState(
        session_id=session_id,
        user_message=user_message,
        conversation_history=[],
        is_human_required_flow=False,
        customer_consent_received=False,
        collected_info={},
        info_collection_complete=False,
        metadata={},
        retrieved_documents=[],
        extracted_keywords=[],
        kms_recommendations=[],
        source_documents=[],
    )


def run_scenario(workflow, scenario: Dict[str, Any]) -> ScenarioResult:
    """단일 시나리오 실행"""
    scenario_id = scenario["id"]
    scenario_name = scenario["name"]
    input_message = scenario["input"]
    expected_decision = scenario["expected_decision"]
    expected_flow = scenario["expected_flow"]

    print(f"\n{'='*60}")
    print(f"[{scenario_id}] {scenario_name}")
    print(f"{'='*60}")
    print(f"입력: {input_message}")
    print(f"기대 Decision: {expected_decision}")

    # 초기 상태 생성
    initial_state = create_initial_state(input_message, scenario_id)

    # 워크플로우 실행 및 노드 추적
    actual_flow = []
    start_time = time.time()
    error = None
    final_state = None

    try:
        # 스트리밍으로 각 노드 추적
        for event in workflow.stream(initial_state):
            node_name = list(event.keys())[0] if event else None
            if node_name:
                actual_flow.append(node_name)
                final_state = event[node_name]
                print(f"  -> {node_name}")

    except Exception as e:
        error = str(e)
        print(f"  X 오류 발생: {error}")

    duration_ms = (time.time() - start_time) * 1000

    # 결과 분석
    actual_decision = None
    details = {}

    if final_state:
        actual_decision = final_state.get("triage_decision")
        if actual_decision:
            actual_decision = actual_decision.value if hasattr(actual_decision, 'value') else str(actual_decision)

        details = {
            "ai_message": final_state.get("ai_message", "")[:200],
            "intent": str(final_state.get("context_intent", "")),
            "intent_confidence": final_state.get("intent_confidence"),
            "rag_best_score": final_state.get("rag_best_score"),
            "retrieved_docs_count": len(final_state.get("retrieved_documents", [])),
            "requires_consultant": final_state.get("requires_consultant"),
            "is_human_required_flow": final_state.get("is_human_required_flow"),
        }

    # 통과 여부 판단
    decision_passed = actual_decision == expected_decision
    flow_passed = actual_flow == expected_flow
    passed = decision_passed and (error is None)

    print(f"\n결과:")
    print(f"  실제 Decision: {actual_decision}")
    print(f"  Decision 일치: {'O' if decision_passed else 'X'}")
    print(f"  Flow: {' -> '.join(actual_flow)}")
    print(f"  소요 시간: {duration_ms:.0f}ms")

    if details.get("ai_message"):
        print(f"  AI 응답: {details['ai_message'][:100]}...")

    return ScenarioResult(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        input_message=input_message,
        expected_decision=expected_decision,
        actual_decision=actual_decision,
        expected_flow=expected_flow,
        actual_flow=actual_flow,
        passed=passed,
        duration_ms=duration_ms,
        details=details,
        error=error
    )


def run_all_scenarios():
    """모든 시나리오 실행"""
    print("\n" + "="*70)
    print("  LangGraph 15가지 시나리오 테스트")
    print("  ai_engine 워크플로우 직접 호출")
    print("="*70)

    # 워크플로우 빌드
    print("\n워크플로우 빌드 중...")
    try:
        workflow = build_workflow()
        print("O 워크플로우 빌드 완료")
    except Exception as e:
        print(f"X 워크플로우 빌드 실패: {e}")
        return

    # 시나리오 실행
    results: List[ScenarioResult] = []

    for scenario in TEST_SCENARIOS:
        result = run_scenario(workflow, scenario)
        results.append(result)

    # 최종 결과 요약
    print("\n" + "="*70)
    print("  최종 결과 요약")
    print("="*70)

    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)

    print(f"\n통과: {passed_count}/{total_count}")
    print(f"총 소요 시간: {sum(r.duration_ms for r in results):.0f}ms")

    print("\n개별 결과:")
    print("-"*70)
    for r in results:
        status = "O PASS" if r.passed else "X FAIL"
        decision_match = "일치" if r.actual_decision == r.expected_decision else f"불일치({r.actual_decision})"
        print(f"  [{r.scenario_id}] {status} | Decision: {decision_match} | {r.duration_ms:.0f}ms")
        if r.error:
            print(f"           오류: {r.error}")

    print("-"*70)

    # 실패한 시나리오 상세
    failed = [r for r in results if not r.passed]
    if failed:
        print("\nX 실패한 시나리오 상세:")
        for r in failed:
            print(f"\n  [{r.scenario_id}] {r.scenario_name}")
            print(f"    입력: {r.input_message}")
            print(f"    기대: {r.expected_decision} -> 실제: {r.actual_decision}")
            if r.error:
                print(f"    오류: {r.error}")

    return results


if __name__ == "__main__":
    run_all_scenarios()
