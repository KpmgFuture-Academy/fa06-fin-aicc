"""
대화형 LangGraph 테스트 CLI
============================

터미널에서 직접 메시지를 입력하고 AI 응답을 확인할 수 있습니다.
"""

import sys
import io
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Windows 콘솔 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.graph.workflow import build_workflow
from ai_engine.graph.state import GraphState


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


def run_single_query(workflow, user_message: str, session_id: str = "interactive") -> Dict[str, Any]:
    """단일 쿼리 실행"""
    initial_state = create_initial_state(user_message, session_id)

    # 워크플로우 실행
    flow = []
    final_state = None

    for event in workflow.stream(initial_state):
        node_name = list(event.keys())[0] if event else None
        if node_name:
            flow.append(node_name)
            final_state = event[node_name]

    return {
        "flow": flow,
        "final_state": final_state
    }


def evaluate_langgraph(flow: list, decision: str, final_state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph 워크플로우 평가 (흐름 제어 중심)"""
    evaluations = []
    passed = True

    # 1. Flow 정상 실행 평가
    expected_flow = ["triage_agent", "answer_agent", "chat_db_storage"]
    if flow == expected_flow:
        evaluations.append(("Flow 정상 실행", "PASS", f"{' -> '.join(flow)}"))
    elif len(flow) >= 3 and flow[0] == "triage_agent":
        evaluations.append(("Flow 정상 실행", "WARN", f"예상과 다름: {' -> '.join(flow)}"))
    else:
        evaluations.append(("Flow 정상 실행", "FAIL", f"비정상 흐름: {' -> '.join(flow)}"))
        passed = False

    # 2. Decision 분기 평가
    valid_decisions = ["SIMPLE_ANSWER", "AUTO_ANSWER", "NEED_MORE_INFO", "HUMAN_REQUIRED"]
    if decision in valid_decisions:
        evaluations.append(("Decision 분기", "PASS", f"유효한 분기: {decision}"))
    else:
        evaluations.append(("Decision 분기", "FAIL", f"유효하지 않은 분기: {decision}"))
        passed = False

    # 3. State 전달 평가 (필수 필드 확인)
    required_fields = ["triage_decision", "ai_message", "session_id"]
    missing_fields = [f for f in required_fields if not final_state.get(f)]
    if not missing_fields:
        evaluations.append(("State 전달", "PASS", "필수 필드 모두 전달됨"))
    else:
        evaluations.append(("State 전달", "FAIL", f"누락된 필드: {missing_fields}"))
        passed = False

    # 4. 오류 없이 완료 평가
    error_message = final_state.get("error_message")
    if not error_message:
        evaluations.append(("오류 없음", "PASS", "예외 없이 완료"))
    else:
        evaluations.append(("오류 없음", "FAIL", f"오류 발생: {error_message}"))
        passed = False

    return {
        "passed": passed,
        "evaluations": evaluations
    }


def print_result(result: Dict[str, Any], duration_ms: float):
    """결과 출력"""
    final_state = result.get("final_state", {}) or {}
    flow = result.get("flow", [])

    # Decision
    triage_decision = final_state.get("triage_decision")
    if triage_decision:
        decision = triage_decision.value if hasattr(triage_decision, 'value') else str(triage_decision)
    else:
        decision = "N/A"

    # AI 응답
    ai_message = final_state.get("ai_message", "")

    # Intent (참고 정보)
    context_intent = final_state.get("context_intent", "")
    intent_confidence = final_state.get("intent_confidence", 0) or 0

    # RAG 정보 (참고 정보)
    rag_best_score = final_state.get("rag_best_score", 0) or 0
    retrieved_docs = final_state.get("retrieved_documents", [])

    # LangGraph 평가 수행
    eval_result = evaluate_langgraph(flow, decision, final_state)

    print("\n" + "="*70)
    print("[ LangGraph 워크플로우 검증 결과 ]")
    print("="*70)

    print("\n[ 평가 항목 ]")
    print("-"*70)
    for name, status, detail in eval_result["evaluations"]:
        if status == "PASS":
            icon = "O"
        elif status == "WARN":
            icon = "!"
        else:
            icon = "X"
        print(f"  [{icon}] {name}: {detail}")

    overall = "PASS" if eval_result["passed"] else "FAIL"
    print(f"\n  >>> LangGraph 검증: {overall}")

    print("\n" + "-"*70)
    print("[ 참고 정보 ]")
    print("-"*70)
    print(f"  Decision: {decision}")
    print(f"  Intent: {context_intent} (신뢰도: {intent_confidence:.1%})" if intent_confidence else f"  Intent: {context_intent}")
    print(f"  RAG 최고 점수: {rag_best_score:.4f}" if rag_best_score else "  RAG 최고 점수: N/A")
    print(f"  검색된 문서: {len(retrieved_docs)}개")
    print(f"  소요 시간: {duration_ms:.0f}ms")

    print("\n" + "-"*70)
    print("[ AI 응답 ]")
    print("-"*70)
    print(ai_message)
    print("="*70)


def main():
    print("\n" + "="*60)
    print("  LangGraph 대화형 테스트 CLI")
    print("  'quit' 또는 'q' 입력 시 종료")
    print("="*60)

    # 워크플로우 빌드
    print("\n워크플로우 빌드 중...")
    try:
        workflow = build_workflow()
        print("워크플로우 빌드 완료\n")
    except Exception as e:
        print(f"워크플로우 빌드 실패: {e}")
        return

    session_count = 0

    while True:
        try:
            user_input = input("\n[입력] > ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'q', 'exit']:
                print("\n종료합니다.")
                break

            session_count += 1
            session_id = f"interactive_{session_count}"

            print(f"\n처리 중... (session: {session_id})")

            start_time = time.time()
            result = run_single_query(workflow, user_input, session_id)
            duration_ms = (time.time() - start_time) * 1000

            print_result(result, duration_ms)

        except KeyboardInterrupt:
            print("\n\n종료합니다.")
            break
        except Exception as e:
            print(f"\n오류 발생: {e}")


if __name__ == "__main__":
    main()
