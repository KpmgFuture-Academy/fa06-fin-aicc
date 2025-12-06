"""Triage Agent 디버깅 테스트 스크립트

이 스크립트는 triage_agent의 판단 과정을 상세히 로깅하여 다음을 확인합니다:
1. RAG 검색이 실제로 실행되고 결과가 있는지
2. 유사도 점수가 0.2 이상인데도 HUMAN_REQUIRED로 판단되는지
3. LLM 응답 로그에서 실제 판단 근거 확인
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ai_engine.graph.workflow import build_workflow
from ai_engine.graph.state import GraphState
from app.schemas.common import TriageDecisionType

# 로깅 설정 (상세 로그 출력)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 특정 모듈의 로그 레벨 조정
logging.getLogger("ai_engine.graph.nodes.triage_agent").setLevel(logging.DEBUG)
logging.getLogger("ai_engine.graph.tools.rag_search_tool").setLevel(logging.DEBUG)
logging.getLogger("ai_engine.vector_store").setLevel(logging.INFO)  # 너무 상세한 로그는 INFO로

async def test_triage_decision(user_message: str, session_id: str = "test_session_001"):
    """Triage 판단 테스트"""
    print("\n" + "="*80)
    print(f"테스트 시작: '{user_message}'")
    print("="*80 + "\n")
    
    # 워크플로우 빌드
    workflow = build_workflow()
    
    # 초기 상태 생성
    initial_state: GraphState = {
        "session_id": session_id,
        "user_message": user_message,
        "conversation_history": [],
        "conversation_turn": 1,
        "is_new_turn": True,
    }
    
    # 워크플로우 실행
    print("워크플로우 실행 중...\n")
    final_state = await workflow.ainvoke(initial_state)
    
    # 결과 출력
    print("\n" + "="*80)
    print("최종 결과")
    print("="*80)
    print(f"triage_decision: {final_state.get('triage_decision')}")
    print(f"requires_consultant: {final_state.get('requires_consultant')}")
    print(f"intent: {final_state.get('intent')}")
    print(f"rag_best_score: {final_state.get('rag_best_score')}")
    print(f"rag_low_confidence: {final_state.get('rag_low_confidence')}")
    print(f"검색된 문서 수: {len(final_state.get('retrieved_documents', []))}")
    
    if final_state.get('retrieved_documents'):
        print("\n검색된 문서:")
        for i, doc in enumerate(final_state.get('retrieved_documents', [])[:3], 1):
            print(f"  {i}. 출처: {doc.get('source')}, 페이지: {doc.get('page')}, 점수: {doc.get('score'):.4f}")
            print(f"     내용 미리보기: {doc.get('content', '')[:100]}...")
    
    print(f"\nai_message: {final_state.get('ai_message', '')[:200]}...")
    
    # 문제 분석
    if final_state.get('triage_decision') == TriageDecisionType.HUMAN_REQUIRED:
        best_score = final_state.get('rag_best_score')
        if best_score and best_score >= 0.2:
            print("\n" + "!"*80)
            print("⚠️ 문제 발견: 유사도 점수가 0.2 이상인데도 HUMAN_REQUIRED로 판단됨!")
            print(f"   최고 유사도 점수: {best_score:.4f}")
            print(f"   프롬프트 기준: 유사도 ≥ 0.2이면 AUTO_HANDLE_OK 권장")
            print("!"*80)
    
    print("\n" + "="*80 + "\n")
    
    return final_state

async def main():
    """메인 함수"""
    # 테스트 케이스들
    test_cases = [
        "자동차보험 관련해서 문의하고 싶은 게 있는데",
        "대출 금리가 궁금해요",
        "예금 상품에 대해 알려주세요",
    ]
    
    for test_message in test_cases:
        await test_triage_decision(test_message, f"test_session_{test_cases.index(test_message) + 1}")
        print("\n\n")

if __name__ == "__main__":
    asyncio.run(main())



