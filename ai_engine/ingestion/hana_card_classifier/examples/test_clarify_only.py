"""
Clarification Loop 단독 테스트 스크립트
======================================

LLMClarifyService만 단독으로 테스트

Usage:
    cd C:\\Users\\Admin\\workplace\\Final_Project\\Hana_Card_GitHub
    python -m examples.test_clarify_only

    # 실제 Claude API 사용
    python -m examples.test_clarify_only --real-api
"""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """메인 테스트 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Clarification Loop 단독 테스트")
    parser.add_argument("--real-api", action="store_true", help="실제 Claude API 사용")
    args = parser.parse_args()

    print("=" * 60)
    print("  Clarification Loop 단독 테스트")
    print("=" * 60)
    print(f"Mode: {'Real Claude API' if args.real_api else 'Mock'}")
    print()

    # 서비스 초기화
    from nlu_category.llm_clarify import create_clarify_service
    from nlu_category.conversation_utils import (
        create_conversation,
        add_clarify_turn,
        build_effective_query,
    )

    clarify_service = create_clarify_service(mock_mode=not args.real_api)

    # 테스트 케이스
    test_cases = [
        {
            "query": "카드 문의",
            "top3": [
                {"label": "카드이용_한도상향", "prob": 0.08},
                {"label": "카드이용_분실신고", "prob": 0.07},
                {"label": "결제_결제일변경", "prob": 0.06},
            ],
        },
        {
            "query": "결제가 안 돼요",
            "top3": [
                {"label": "결제_결제오류", "prob": 0.09},
                {"label": "카드이용_사용정지", "prob": 0.05},
                {"label": "결제_한도초과", "prob": 0.04},
            ],
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Query: {case['query']}")
        print("-" * 50)

        # Conversation 생성
        conversation = create_conversation(
            original_query=case["query"],
            max_retry=3,
        )

        # need_clarify 체크
        decision = clarify_service.need_clarify(
            confidence_pattern="B",
            retry_count=0,
        )
        print(f"Need Clarify: {decision['should_clarify']}")
        print(f"Reason: {decision['reason']}")

        if decision["should_clarify"]:
            # 질문 생성
            effective_query = build_effective_query(conversation)
            result = clarify_service.generate_question(
                effective_query=effective_query,
                electra_top3=case["top3"],
                conversation=conversation,
            )

            print(f"\nGenerated Question:")
            print(f"  → {result['clarify_question']}")

            # Mock 답변 추가
            mock_answer = "한도 상향 문의입니다"
            conversation = add_clarify_turn(
                conversation=conversation,
                question=result["clarify_question"],
                answer=mock_answer,
            )

            # effective_query 확인
            new_effective_query = build_effective_query(conversation)
            print(f"\nEffective Query after answer:")
            print(f"  → {new_effective_query}")

        print("-" * 50)

    print("\n" + "=" * 60)
    print("  테스트 완료")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
