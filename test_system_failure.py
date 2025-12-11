"""
시스템 장애 시나리오 테스트
===========================

LangGraph 워크플로우의 에러 핸들링 검증
- LLM API 타임아웃
- LLM API 오류 (연결 실패, 할당량 초과)
- RAG 검색 실패
- Intent 분류 실패
"""

import sys
import io
import time
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# Windows 콘솔 인코딩 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.graph.workflow import build_workflow
from ai_engine.graph.state import GraphState


@dataclass
class FailureTestResult:
    """장애 테스트 결과"""
    test_name: str
    failure_type: str
    graceful_handling: bool  # 우아하게 처리되었는가
    error_message_shown: bool  # 사용자에게 에러 메시지가 표시되었는가
    flow_completed: bool  # 플로우가 완료되었는가 (에러 발생해도)
    ai_message: str
    details: Dict[str, Any]


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


def test_llm_timeout():
    """LLM API 타임아웃 테스트"""
    print("\n" + "="*60)
    print("[테스트 1] LLM API 타임아웃")
    print("="*60)

    from openai import APITimeoutError

    workflow = build_workflow()
    initial_state = create_initial_state("결제일 알려줘", "timeout_test")

    # LLM 호출 시 타임아웃 발생 시뮬레이션
    with patch('ai_engine.graph.nodes.answer_agent.llm') as mock_llm:
        mock_llm.invoke.side_effect = APITimeoutError(request=MagicMock())

        try:
            final_state = None
            flow = []
            for event in workflow.stream(initial_state):
                node_name = list(event.keys())[0] if event else None
                if node_name:
                    flow.append(node_name)
                    final_state = event[node_name]

            ai_message = final_state.get("ai_message", "") if final_state else ""
            graceful = "타임아웃" in ai_message or "시간" in ai_message or "다시 시도" in ai_message

            print(f"Flow: {' -> '.join(flow)}")
            print(f"AI 응답: {ai_message[:100]}...")
            print(f"우아한 처리: {'O' if graceful else 'X'}")

            return FailureTestResult(
                test_name="LLM API 타임아웃",
                failure_type="timeout",
                graceful_handling=graceful,
                error_message_shown=bool(ai_message),
                flow_completed=len(flow) >= 3,
                ai_message=ai_message,
                details={"flow": flow}
            )
        except Exception as e:
            print(f"예외 발생: {e}")
            return FailureTestResult(
                test_name="LLM API 타임아웃",
                failure_type="timeout",
                graceful_handling=False,
                error_message_shown=False,
                flow_completed=False,
                ai_message="",
                details={"error": str(e)}
            )


def test_llm_connection_error():
    """LLM API 연결 오류 테스트"""
    print("\n" + "="*60)
    print("[테스트 2] LLM API 연결 오류")
    print("="*60)

    from openai import APIConnectionError

    workflow = build_workflow()
    initial_state = create_initial_state("한도 조회해줘", "connection_test")

    with patch('ai_engine.graph.nodes.answer_agent.llm') as mock_llm:
        mock_llm.invoke.side_effect = APIConnectionError(request=MagicMock())

        try:
            final_state = None
            flow = []
            for event in workflow.stream(initial_state):
                node_name = list(event.keys())[0] if event else None
                if node_name:
                    flow.append(node_name)
                    final_state = event[node_name]

            ai_message = final_state.get("ai_message", "") if final_state else ""
            graceful = "연결" in ai_message or "서버" in ai_message or "오류" in ai_message

            print(f"Flow: {' -> '.join(flow)}")
            print(f"AI 응답: {ai_message[:100]}...")
            print(f"우아한 처리: {'O' if graceful else 'X'}")

            return FailureTestResult(
                test_name="LLM API 연결 오류",
                failure_type="connection_error",
                graceful_handling=graceful,
                error_message_shown=bool(ai_message),
                flow_completed=len(flow) >= 3,
                ai_message=ai_message,
                details={"flow": flow}
            )
        except Exception as e:
            print(f"예외 발생: {e}")
            return FailureTestResult(
                test_name="LLM API 연결 오류",
                failure_type="connection_error",
                graceful_handling=False,
                error_message_shown=False,
                flow_completed=False,
                ai_message="",
                details={"error": str(e)}
            )


def test_llm_rate_limit():
    """LLM API 할당량 초과 테스트"""
    print("\n" + "="*60)
    print("[테스트 3] LLM API 할당량 초과 (429)")
    print("="*60)

    from openai import RateLimitError

    workflow = build_workflow()
    initial_state = create_initial_state("포인트 확인해줘", "rate_limit_test")

    with patch('ai_engine.graph.nodes.answer_agent.llm') as mock_llm:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_llm.invoke.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body=None
        )

        try:
            final_state = None
            flow = []
            for event in workflow.stream(initial_state):
                node_name = list(event.keys())[0] if event else None
                if node_name:
                    flow.append(node_name)
                    final_state = event[node_name]

            ai_message = final_state.get("ai_message", "") if final_state else ""
            graceful = "사용량" in ai_message or "초과" in ai_message or "잠시 후" in ai_message

            print(f"Flow: {' -> '.join(flow)}")
            print(f"AI 응답: {ai_message[:100]}...")
            print(f"우아한 처리: {'O' if graceful else 'X'}")

            return FailureTestResult(
                test_name="LLM API 할당량 초과",
                failure_type="rate_limit",
                graceful_handling=graceful,
                error_message_shown=bool(ai_message),
                flow_completed=len(flow) >= 3,
                ai_message=ai_message,
                details={"flow": flow}
            )
        except Exception as e:
            print(f"예외 발생: {e}")
            return FailureTestResult(
                test_name="LLM API 할당량 초과",
                failure_type="rate_limit",
                graceful_handling=False,
                error_message_shown=False,
                flow_completed=False,
                ai_message="",
                details={"error": str(e)}
            )


def test_rag_search_failure():
    """RAG 검색 실패 테스트"""
    print("\n" + "="*60)
    print("[테스트 4] RAG 검색 실패 (Vector Store 오류)")
    print("="*60)

    workflow = build_workflow()
    initial_state = create_initial_state("카드 분실 신고해줘", "rag_failure_test")

    with patch('ai_engine.graph.nodes.triage_agent.rag_search_tool') as mock_rag:
        mock_rag.side_effect = Exception("ChromaDB connection failed")

        try:
            final_state = None
            flow = []
            for event in workflow.stream(initial_state):
                node_name = list(event.keys())[0] if event else None
                if node_name:
                    flow.append(node_name)
                    final_state = event[node_name]

            ai_message = final_state.get("ai_message", "") if final_state else ""
            # RAG 실패해도 응답이 생성되면 우아한 처리
            graceful = bool(ai_message) and len(ai_message) > 10

            print(f"Flow: {' -> '.join(flow)}")
            print(f"AI 응답: {ai_message[:100]}..." if ai_message else "AI 응답: 없음")
            print(f"우아한 처리: {'O' if graceful else 'X'}")

            return FailureTestResult(
                test_name="RAG 검색 실패",
                failure_type="rag_error",
                graceful_handling=graceful,
                error_message_shown=bool(ai_message),
                flow_completed=len(flow) >= 3,
                ai_message=ai_message,
                details={"flow": flow}
            )
        except Exception as e:
            print(f"예외 발생: {e}")
            return FailureTestResult(
                test_name="RAG 검색 실패",
                failure_type="rag_error",
                graceful_handling=False,
                error_message_shown=False,
                flow_completed=False,
                ai_message="",
                details={"error": str(e)}
            )


def test_intent_classification_failure():
    """Intent 분류 실패 테스트"""
    print("\n" + "="*60)
    print("[테스트 5] Intent 분류 실패 (모델 오류)")
    print("="*60)

    workflow = build_workflow()
    initial_state = create_initial_state("대출 상담 받고 싶어요", "intent_failure_test")

    with patch('ai_engine.graph.nodes.triage_agent.intent_classification_tool') as mock_intent:
        mock_intent.side_effect = Exception("Model loading failed")

        try:
            final_state = None
            flow = []
            for event in workflow.stream(initial_state):
                node_name = list(event.keys())[0] if event else None
                if node_name:
                    flow.append(node_name)
                    final_state = event[node_name]

            ai_message = final_state.get("ai_message", "") if final_state else ""
            graceful = bool(ai_message) and len(ai_message) > 10

            print(f"Flow: {' -> '.join(flow)}")
            print(f"AI 응답: {ai_message[:100]}..." if ai_message else "AI 응답: 없음")
            print(f"우아한 처리: {'O' if graceful else 'X'}")

            return FailureTestResult(
                test_name="Intent 분류 실패",
                failure_type="intent_error",
                graceful_handling=graceful,
                error_message_shown=bool(ai_message),
                flow_completed=len(flow) >= 3,
                ai_message=ai_message,
                details={"flow": flow}
            )
        except Exception as e:
            print(f"예외 발생: {e}")
            return FailureTestResult(
                test_name="Intent 분류 실패",
                failure_type="intent_error",
                graceful_handling=False,
                error_message_shown=False,
                flow_completed=False,
                ai_message="",
                details={"error": str(e)}
            )


def test_empty_input():
    """빈 입력 처리 테스트"""
    print("\n" + "="*60)
    print("[테스트 6] 빈 입력 처리")
    print("="*60)

    workflow = build_workflow()
    initial_state = create_initial_state("", "empty_input_test")

    try:
        final_state = None
        flow = []
        for event in workflow.stream(initial_state):
            node_name = list(event.keys())[0] if event else None
            if node_name:
                flow.append(node_name)
                final_state = event[node_name]

        ai_message = final_state.get("ai_message", "") if final_state else ""
        graceful = bool(ai_message) and ("무엇" in ai_message or "도와" in ai_message or "말씀" in ai_message)

        print(f"Flow: {' -> '.join(flow)}")
        print(f"AI 응답: {ai_message[:100]}..." if ai_message else "AI 응답: 없음")
        print(f"우아한 처리: {'O' if graceful else 'X'}")

        return FailureTestResult(
            test_name="빈 입력 처리",
            failure_type="empty_input",
            graceful_handling=graceful,
            error_message_shown=bool(ai_message),
            flow_completed=len(flow) >= 3,
            ai_message=ai_message,
            details={"flow": flow}
        )
    except Exception as e:
        print(f"예외 발생: {e}")
        return FailureTestResult(
            test_name="빈 입력 처리",
            failure_type="empty_input",
            graceful_handling=False,
            error_message_shown=False,
            flow_completed=False,
            ai_message="",
            details={"error": str(e)}
        )


def test_very_long_input():
    """매우 긴 입력 처리 테스트"""
    print("\n" + "="*60)
    print("[테스트 7] 매우 긴 입력 처리")
    print("="*60)

    workflow = build_workflow()
    long_input = "카드 한도 올려주세요. " * 500  # 매우 긴 입력
    initial_state = create_initial_state(long_input, "long_input_test")

    try:
        start_time = time.time()
        final_state = None
        flow = []
        for event in workflow.stream(initial_state):
            node_name = list(event.keys())[0] if event else None
            if node_name:
                flow.append(node_name)
                final_state = event[node_name]
        duration = time.time() - start_time

        ai_message = final_state.get("ai_message", "") if final_state else ""
        graceful = bool(ai_message) and len(ai_message) > 10

        print(f"Flow: {' -> '.join(flow)}")
        print(f"입력 길이: {len(long_input)} 문자")
        print(f"처리 시간: {duration:.2f}초")
        print(f"AI 응답: {ai_message[:100]}..." if ai_message else "AI 응답: 없음")
        print(f"우아한 처리: {'O' if graceful else 'X'}")

        return FailureTestResult(
            test_name="매우 긴 입력 처리",
            failure_type="long_input",
            graceful_handling=graceful,
            error_message_shown=bool(ai_message),
            flow_completed=len(flow) >= 3,
            ai_message=ai_message,
            details={"flow": flow, "input_length": len(long_input), "duration": duration}
        )
    except Exception as e:
        print(f"예외 발생: {e}")
        return FailureTestResult(
            test_name="매우 긴 입력 처리",
            failure_type="long_input",
            graceful_handling=False,
            error_message_shown=False,
            flow_completed=False,
            ai_message="",
            details={"error": str(e)}
        )


def run_all_failure_tests():
    """모든 장애 테스트 실행"""
    print("\n" + "="*70)
    print("  시스템 장애 시나리오 테스트")
    print("  LangGraph 에러 핸들링 검증")
    print("="*70)

    results = []

    # 1. LLM 타임아웃
    results.append(test_llm_timeout())

    # 2. LLM 연결 오류
    results.append(test_llm_connection_error())

    # 3. LLM 할당량 초과
    results.append(test_llm_rate_limit())

    # 4. RAG 검색 실패
    results.append(test_rag_search_failure())

    # 5. Intent 분류 실패
    results.append(test_intent_classification_failure())

    # 6. 빈 입력
    results.append(test_empty_input())

    # 7. 매우 긴 입력
    results.append(test_very_long_input())

    # 결과 요약
    print("\n" + "="*70)
    print("  테스트 결과 요약")
    print("="*70)

    passed = 0
    for r in results:
        status = "PASS" if r.graceful_handling else "FAIL"
        if r.graceful_handling:
            passed += 1
        print(f"  [{status}] {r.test_name}")
        if not r.graceful_handling:
            print(f"       - 우아한 처리: X")
            print(f"       - 에러 메시지: {'O' if r.error_message_shown else 'X'}")
            print(f"       - 플로우 완료: {'O' if r.flow_completed else 'X'}")

    print("-"*70)
    print(f"  통과: {passed}/{len(results)}")
    print("="*70)

    return results


if __name__ == "__main__":
    run_all_failure_tests()
