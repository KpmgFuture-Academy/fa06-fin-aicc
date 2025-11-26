"""
LLM Refine 단독 테스트 스크립트
==============================

LLMRefineService만 단독으로 테스트

Usage:
    cd C:\\Users\\Admin\\workplace\\Final_Project\\Hana_Card_GitHub
    python -m examples.test_refine_only

    # 실제 Claude API 사용
    python -m examples.test_refine_only --real-api
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

    parser = argparse.ArgumentParser(description="LLM Refine 단독 테스트")
    parser.add_argument("--real-api", action="store_true", help="실제 Claude API 사용")
    args = parser.parse_args()

    print("=" * 60)
    print("  LLM Refine 단독 테스트")
    print("=" * 60)
    print(f"Mode: {'Real Claude API' if args.real_api else 'Mock'}")
    print()

    # 서비스 초기화
    from nlu_category.llm_refine import create_llm_refine_service

    refine_service = create_llm_refine_service(mock_mode=not args.real_api)

    # 테스트 케이스
    test_cases = [
        {
            "effective_query": "카드 문의 한도 상향 문의입니다 영구 증액이요",
            "top3": [
                {"label": "카드이용_한도상향_영구증액", "prob": 0.08},
                {"label": "카드이용_한도상향_일시증액", "prob": 0.07},
                {"label": "결제_결제일변경", "prob": 0.03},
            ],
        },
        {
            "effective_query": "카드를 잃어버렸어요 사용 정지해주세요",
            "top3": [
                {"label": "분실도난_분실신고", "prob": 0.09},
                {"label": "분실도난_사용정지", "prob": 0.08},
                {"label": "카드이용_재발급", "prob": 0.04},
            ],
        },
        {
            "effective_query": "이번 달 결제 금액이 얼마인지 알고 싶어요",
            "top3": [
                {"label": "결제_결제금액조회", "prob": 0.07},
                {"label": "결제_명세서발급", "prob": 0.06},
                {"label": "결제_결제내역조회", "prob": 0.05},
            ],
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n[Test {i}]")
        print(f"Effective Query: {case['effective_query']}")
        print("-" * 50)

        # Top3 출력
        print("Top3 Candidates:")
        for j, item in enumerate(case["top3"], 1):
            print(f"  {j}. {item['label']} ({item['prob']*100:.1f}%)")

        # LLM Refine 실행
        result = refine_service.refine(
            effective_query=case["effective_query"],
            electra_top3=case["top3"],
        )

        print(f"\nLLM Refine Result:")
        print(f"  Selected Category : {result['selected_category']}")
        print(f"  Confidence        : {result['confidence']:.1f}%")
        print(f"  Reason            : {result['reason']}")

        print("-" * 50)

    print("\n" + "=" * 60)
    print("  테스트 완료")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
