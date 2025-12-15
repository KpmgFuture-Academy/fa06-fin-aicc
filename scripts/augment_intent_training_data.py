"""Intent 분류 모델 학습 데이터 보강 스크립트 (Option D - Full Improvement)

38개 카테고리에 대한 학습 데이터를 대폭 보강하여 모델 성능을 개선합니다.

주요 기능:
1. F1=0 카테고리 데이터 생성 (긴급배송, 전화요금, 청구지 등)
2. Support<100 저성능 카테고리 보강
3. LLM 기반 합성 데이터 생성 (OpenAI API 사용)
4. Back-translation 패러프레이징
5. 데이터 밸런싱 및 전처리

사용법:
    python scripts/augment_intent_training_data.py --all           # 전체 데이터 보강 (Option D)
    python scripts/augment_intent_training_data.py --step 1        # Step 1만 실행
    python scripts/augment_intent_training_data.py --analyze       # 현재 데이터 분석만
"""

from __future__ import annotations

import json
import random
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# 38개 카테고리 정의 (id2intent.json 기반)
# =============================================================================

INTENT_CATEGORIES = {
    0: "가상계좌 안내",
    1: "가상계좌 예약/취소",
    2: "결제계좌 안내/변경",
    3: "결제대금 안내",
    4: "결제일 안내/변경",
    5: "교육비",
    6: "금리인하요구권 안내/신청",
    7: "기타",
    8: "긴급 배송 신청",
    9: "단기카드대출 안내/실행",
    10: "도난/분실 신청/해제",
    11: "도시가스",
    12: "매출구분 변경",
    13: "선결제/즉시출금",
    14: "쇼핑케어",
    15: "승인취소/매출취소 안내",
    16: "신용공여기간 안내",
    17: "심사 진행사항 안내",
    18: "연체대금 안내",
    19: "연체대금 즉시출금",
    20: "연회비 안내",
    21: "오토할부/오토캐쉬백 안내/신청/취소",
    22: "이벤트 안내",
    23: "이용내역 안내",
    24: "이용방법 안내",
    25: "일부결제대금이월약정 안내",
    26: "일부결제대금이월약정 해지",
    27: "입금내역 안내",
    28: "장기카드대출 안내",
    29: "전화요금",
    30: "정부지원 바우처 (등유, 임신 등)",
    31: "증명서/확인서 발급",
    32: "청구지 안내/변경",
    33: "포인트/마일리지 안내",
    34: "포인트/마일리지 전환등록",
    35: "프리미엄 바우처 안내/발급",
    36: "한도 안내",
    37: "한도상향 접수/처리",
}

# 현재 모델 평가 결과 기반 카테고리별 성능 정보
CATEGORY_PERFORMANCE = {
    # F1=0 카테고리 (최우선 보강)
    "긴급 배송 신청": {"f1": 0.00, "support": 0, "priority": 1},
    "전화요금": {"f1": 0.00, "support": 25, "priority": 1},
    "청구지 안내/변경": {"f1": 0.00, "support": 54, "priority": 1},
    "기타": {"f1": 0.00, "support": 44, "priority": 1},

    # 매우 낮은 F1 (Support<100, F1<0.5)
    "입금내역 안내": {"f1": 0.23, "support": 86, "priority": 2},
    "포인트/마일리지 안내": {"f1": 0.32, "support": 115, "priority": 2},
    "신용공여기간 안내": {"f1": 0.34, "support": 33, "priority": 2},
    "증명서/확인서 발급": {"f1": 0.38, "support": 68, "priority": 2},
    "연체대금 안내": {"f1": 0.40, "support": 105, "priority": 2},
    "결제대금 안내": {"f1": 0.45, "support": 492, "priority": 2},
    "한도 안내": {"f1": 0.50, "support": 154, "priority": 2},

    # 중간 성능 (Support<100, F1<0.7)
    "포인트/마일리지 전환등록": {"f1": 0.54, "support": 78, "priority": 3},
    "매출구분 변경": {"f1": 0.58, "support": 99, "priority": 3},
    "쇼핑케어": {"f1": 0.60, "support": 18, "priority": 3},
    "프리미엄 바우처 안내/발급": {"f1": 0.60, "support": 81, "priority": 3},
    "이용방법 안내": {"f1": 0.63, "support": 394, "priority": 3},
    "일부결제대금이월약정 안내": {"f1": 0.66, "support": 124, "priority": 3},
    "이용내역 안내": {"f1": 0.66, "support": 1333, "priority": 3},
    "연회비 안내": {"f1": 0.67, "support": 36, "priority": 3},
}


# =============================================================================
# Step 1: 템플릿 기반 데이터 생성 (F1=0 카테고리)
# =============================================================================

# 카테고리별 발화 템플릿
UTTERANCE_TEMPLATES = {
    "긴급 배송 신청": [
        "카드 긴급 배송 신청하고 싶어요",
        "긴급 배송으로 카드 받고 싶습니다",
        "급하게 카드가 필요한데 빨리 받을 수 있나요",
        "카드 빨리 받을 수 있는 방법 있나요",
        "오늘 내로 카드 받을 수 있나요",
        "긴급 카드 배송 가능한가요",
        "급한데 카드 당일 배송 되나요",
        "빠른 배송으로 카드 신청하고 싶어요",
        "카드 익일 배송 신청하려고요",
        "퀵 서비스로 카드 받을 수 있나요",
        "카드 빠른 수령 방법 알려주세요",
        "신규 카드 급하게 필요합니다",
        "재발급 카드 긴급 배송 요청합니다",
        "분실 카드 긴급 재발급 해주세요",
        "당일 카드 수령 가능한가요",
        "빠른 카드 발급 방법이 있나요",
        "급행 배송으로 카드 받고 싶어요",
        "특급 배송 카드 신청합니다",
        "오늘 중으로 카드 받아야 하는데요",
        "내일까지 카드가 꼭 필요해요",
    ],

    "전화요금": [
        "전화요금 카드로 납부하고 싶어요",
        "통신비 자동이체 신청하려고요",
        "휴대폰 요금 카드 결제 방법 알려주세요",
        "전화비 카드로 내는 방법이요",
        "통신요금 카드 납부 가능한가요",
        "핸드폰 요금 자동결제 등록하고 싶어요",
        "인터넷 요금 카드로 낼 수 있나요",
        "KT 요금 카드 자동이체 신청이요",
        "SKT 통신비 카드 납부 방법",
        "LG유플러스 요금 카드로 내려고요",
        "통신사 요금 자동납부 등록 방법",
        "전화요금 자동이체 해지하려고요",
        "통신비 결제 카드 변경하고 싶어요",
        "휴대폰 요금 할인 카드 있나요",
        "통신요금 포인트로 결제 가능한가요",
        "전화비 청구서가 안 왔어요",
        "통신비 결제일이 언제인가요",
        "핸드폰 요금 미납 확인해주세요",
        "인터넷 요금 카드 납부 신청",
        "IPTV 요금 자동이체 등록하려고요",
    ],

    "청구지 안내/변경": [
        "청구지 주소 변경하고 싶어요",
        "명세서 받는 주소 바꾸려고요",
        "청구서 주소 변경 방법 알려주세요",
        "이사해서 청구지 변경해야 해요",
        "우편 명세서 주소 바꾸고 싶어요",
        "청구지가 어디로 되어있나요",
        "현재 청구지 주소 확인하고 싶어요",
        "명세서 받는 곳 변경 신청이요",
        "청구 주소 수정하려고 합니다",
        "카드 명세서 주소 변경이요",
        "청구지 이메일로 바꾸고 싶어요",
        "우편 청구서 대신 이메일로 받고 싶어요",
        "청구지 모바일로 변경 가능한가요",
        "명세서 수신처 변경하려고요",
        "청구 우편물 주소 바꿔주세요",
        "이사했는데 청구지 어떻게 바꾸나요",
        "새 주소로 청구서 받고 싶어요",
        "청구지 변경 신청 방법이요",
        "명세서 배송지 변경해주세요",
        "청구서 받는 방법 변경하고 싶어요",
    ],

    "기타": [
        "다른 문의사항이 있어요",
        "상담원 연결해주세요",
        "사람이랑 통화하고 싶어요",
        "다른 것 좀 물어볼게요",
        "기타 문의드립니다",
        "이건 어디로 문의해야 하나요",
        "담당 부서 연결 부탁드려요",
        "전문 상담사와 통화하고 싶어요",
        "이 건은 상담원 연결이 필요해요",
        "복잡한 문의인데 상담원 부탁해요",
        "추가 질문이 있습니다",
        "다른 내용으로 문의드려요",
        "이건 카테고리가 뭐죠",
        "어떤 메뉴에서 해야하나요",
        "도움이 더 필요해요",
        "추가 안내 부탁드립니다",
        "이것 말고 다른 거요",
        "아 그게 아니라요",
        "질문이 좀 다른데요",
        "이건 어떻게 해야 하죠",
    ],

    # Priority 2 카테고리 - 추가 템플릿
    "입금내역 안내": [
        "입금내역 확인하고 싶어요",
        "결제한 내역 조회해주세요",
        "카드대금 납부내역 보고 싶어요",
        "이번 달 입금 확인해주세요",
        "결제 입금 내역 조회 방법이요",
        "자동이체 입금 확인하려고요",
        "결제대금 납부 내역 알려주세요",
        "언제 결제됐는지 확인하고 싶어요",
        "입금 처리 내역 확인이요",
        "지난달 납부내역 조회해주세요",
        "카드값 낸 내역 보여주세요",
        "결제 완료 내역 확인",
        "출금된 내역 조회하려고요",
        "자동납부 내역 확인해주세요",
        "이체내역 조회 부탁드려요",
    ],

    "신용공여기간 안내": [
        "신용공여기간이 뭔가요",
        "무이자 기간 알려주세요",
        "결제 유예 기간이 어떻게 되나요",
        "신용공여 기간 조회하고 싶어요",
        "이자 없이 쓸 수 있는 기간이요",
        "신용카드 결제 유예기간 안내해주세요",
        "공여기간 얼마나 되나요",
        "무이자 할부 기간 문의드려요",
        "결제 전 무이자 기간이요",
        "신용공여기간 확인 방법",
        "카드 이자 안 붙는 기간",
        "결제 유예 가능 기간 알려주세요",
        "무이자 가능 기간 조회",
        "신용기간 언제까지인가요",
        "이자 면제 기간 문의",
    ],

    "증명서/확인서 발급": [
        "결제 증명서 발급해주세요",
        "이용확인서 필요합니다",
        "거래내역 확인서 발급하려고요",
        "납부확인서 뽑아주세요",
        "카드 사용 증명서 발급",
        "연말정산용 증명서 필요해요",
        "소득공제용 서류 발급 부탁드려요",
        "사용내역 확인서 어떻게 받나요",
        "영수증 재발급 해주세요",
        "거래증명서 발급 신청이요",
        "납입증명서 필요합니다",
        "카드 이용 확인서 발급해주세요",
        "증빙서류 발급 방법 알려주세요",
        "연체 없음 확인서 발급",
        "거래내역서 출력하고 싶어요",
    ],

    "연체대금 안내": [
        "연체된 금액이 얼마인가요",
        "연체료 확인하고 싶어요",
        "밀린 카드값 얼마나 되나요",
        "연체 이자 얼마나 붙었나요",
        "미납금액 조회해주세요",
        "연체 상태 확인하려고요",
        "카드 연체 내역 알려주세요",
        "연체금 납부 방법이요",
        "연체된 것 있나요",
        "미결제 금액 확인해주세요",
        "연체 이자율이 어떻게 되나요",
        "카드대금 밀린 거 확인",
        "연체 발생했는지 알고 싶어요",
        "미납된 금액 조회",
        "연체 해결 방법 알려주세요",
    ],

    "포인트/마일리지 안내": [
        "포인트 얼마나 있나요",
        "마일리지 조회해주세요",
        "적립 포인트 확인하고 싶어요",
        "현재 포인트 잔액이요",
        "마일리지 얼마 모였나요",
        "포인트 적립 내역 알려주세요",
        "사용 가능한 포인트 확인",
        "마일리지 적립 현황 조회",
        "포인트 유효기간 언제까지인가요",
        "소멸 예정 포인트 있나요",
        "포인트 사용처 알려주세요",
        "마일리지 어디서 쓸 수 있나요",
        "적립 포인트 조회 방법",
        "이번 달 적립된 포인트",
        "포인트 적립률 얼마인가요",
    ],

    "한도 안내": [
        "카드 한도 얼마인가요",
        "이용한도 조회해주세요",
        "현재 사용 가능한 한도",
        "잔여 한도 얼마나 남았나요",
        "총 한도 확인하고 싶어요",
        "일시불 한도 얼마인가요",
        "할부 한도 조회",
        "현금서비스 한도 확인",
        "해외이용 한도 알려주세요",
        "카드론 한도 얼마인가요",
        "이번 달 남은 한도",
        "최대 이용 가능 금액",
        "한도 얼마까지 쓸 수 있나요",
        "카드 이용한도 문의",
        "잔여 이용한도 확인해주세요",
    ],

    # Priority 3 카테고리
    "연회비 안내": [
        "연회비 얼마인가요",
        "연회비 청구 시기 알려주세요",
        "카드 연회비 확인하고 싶어요",
        "연회비 면제 조건 있나요",
        "연회비 할인 방법이요",
        "연회비 납부일이 언제인가요",
        "연회비 환불 가능한가요",
        "연회비 청구 내역 조회",
        "올해 연회비 얼마 나오나요",
        "연회비 면제 카드 있나요",
        "연회비 자동이체 설정",
        "연회비 결제 방법",
        "연회비 언제 빠지나요",
        "다음 연회비 청구일",
        "연회비 할인 프로모션 있나요",
    ],

    # 추가: 나머지 고성능 카테고리도 포함
    "결제일 안내/변경": [
        "결제일이 언제인가요",
        "결제일 확인해주세요",
        "카드 대금 언제 빠지나요",
        "결제일 변경하고 싶어요",
        "결제일 바꿀 수 있나요",
        "결제 언제 되나요",
        "이번 달 결제일 알려주세요",
        "대금 결제일이 며칠인가요",
        "결제일 조회해주세요",
        "카드값 언제 나가나요",
        "결제 예정일 확인",
        "결제일 안내 부탁드려요",
        "매월 결제일이 언제죠",
        "다음 결제일이 언제예요",
        "결제일 변경 방법 알려주세요",
    ],

    "이용내역 안내": [
        "이용내역 확인하고 싶어요",
        "카드 사용내역 보여주세요",
        "어디서 얼마 썼는지 알고 싶어요",
        "카드 내역 조회해주세요",
        "결제 내역 확인",
        "이번 달 사용 내역",
        "지난달 카드 쓴 내역",
        "카드 승인 내역 확인",
        "최근 이용내역 알려주세요",
        "언제 어디서 썼는지 확인",
        "카드 결제 내역 조회",
        "사용한 곳 확인하고 싶어요",
        "이용 내역서 보내주세요",
        "승인 취소 내역도 보이나요",
        "해외 사용 내역 확인",
    ],

    "선결제/즉시출금": [
        "선결제 하고 싶어요",
        "미리 결제할 수 있나요",
        "선입금 방법 알려주세요",
        "즉시 결제하려고요",
        "카드값 미리 내고 싶어요",
        "선납하면 한도 회복되나요",
        "즉시출금 신청",
        "선결제 가능 금액",
        "먼저 결제하는 방법",
        "당일 선결제 가능한가요",
        "가상계좌로 선결제",
        "한도 회복하려면 선결제",
        "선결제 수수료 있나요",
        "즉시 납부 방법",
        "미리 입금하고 싶어요",
    ],

    "도난/분실 신청/해제": [
        "카드 분실 신고하려고요",
        "카드 잃어버렸어요",
        "분실 카드 정지해주세요",
        "도난 신고 접수",
        "카드 도난당했어요",
        "분실 해제하려고요",
        "카드 찾았는데 해제해주세요",
        "분실 정지 풀어주세요",
        "도난 신고 취소",
        "카드 없어졌어요",
        "분실 신고 방법",
        "카드 정지 요청",
        "분실 카드 재발급",
        "긴급 분실 신고",
        "카드 도난 접수 확인",
    ],

    "한도상향 접수/처리": [
        "한도 올려주세요",
        "한도 상향 신청하고 싶어요",
        "카드 한도 높이고 싶어요",
        "한도 증액 요청",
        "이용 한도 올릴 수 있나요",
        "한도 상향 가능한가요",
        "한도 업 신청",
        "한도 늘려주세요",
        "한도 상향 처리 현황",
        "한도 상향 심사 결과",
        "일시적 한도 상향",
        "한도 상향 서류 필요한가요",
        "한도 증액 심사 기간",
        "한도 상향 접수 확인",
        "최대 한도까지 올려주세요",
    ],

    "쇼핑케어": [
        "쇼핑케어 서비스 신청하고 싶어요",
        "물건 AS 보장 서비스 있나요",
        "구매 보호 서비스 문의드려요",
        "쇼핑케어 어떻게 이용하나요",
        "구입한 물건 보험 처리 가능한가요",
        "쇼핑 안심 서비스 안내해주세요",
        "카드 구매 보호 서비스",
        "쇼핑케어 보상 신청",
        "물품 파손 보상 받을 수 있나요",
        "쇼핑케어 혜택 알려주세요",
        "구매 물품 보장 서비스",
        "쇼핑케어 대상 확인",
        "물건 훼손 보상 문의",
        "쇼핑케어 이용 방법",
        "구매 보험 서비스 가입",
    ],

    "포인트/마일리지 전환등록": [
        "포인트 전환하고 싶어요",
        "마일리지 항공사로 전환해주세요",
        "포인트 캐시백 신청",
        "마일리지 전환 방법 알려주세요",
        "포인트 현금으로 바꿀 수 있나요",
        "적립금 전환 신청이요",
        "포인트 제휴사 이동",
        "마일리지 다른 카드로 옮기기",
        "포인트 통합 등록 방법",
        "마일리지 전환 비율 알려주세요",
        "포인트 캐시 전환",
        "대한항공 마일리지 전환",
        "아시아나 마일리지로 바꾸고 싶어요",
        "포인트 쇼핑몰 사용 등록",
        "마일리지 전환 수수료 있나요",
    ],
}


def generate_template_variations(base_template: str, count: int = 5) -> List[str]:
    """템플릿에서 변형된 발화 생성"""
    variations = []

    # 말투 변형
    endings = ["요", "습니다", "ㄹ게요", "고 싶어요", "려고요", "할래요", "해주세요", "부탁드려요"]

    # 필러 추가
    fillers = ["", "저기요 ", "음 ", "그 ", "혹시 ", "어 ", "저 "]

    # 겸손 표현
    humble = ["", "좀 ", "혹시 ", "실례지만 "]

    for _ in range(count):
        text = base_template

        # 필러 추가 (30% 확률)
        if random.random() < 0.3:
            text = random.choice(fillers) + text

        # 겸손 표현 추가 (20% 확률)
        if random.random() < 0.2:
            text = text.replace("하고", random.choice(humble) + "하고")

        # 말투 변경 (일부)
        if random.random() < 0.4:
            for end in endings:
                if text.endswith(end):
                    text = text[:-len(end)] + random.choice(endings)
                    break

        variations.append(text)

    return variations


def generate_step1_data() -> Dict[str, List[str]]:
    """Step 1: F1=0 카테고리에 대한 템플릿 기반 데이터 생성"""
    print("\n" + "=" * 60)
    print("[Step 1] F1=0 카테고리 템플릿 기반 데이터 생성")
    print("=" * 60)

    augmented_data = {}
    target_count = 200  # 카테고리당 목표 샘플 수

    priority1_categories = [cat for cat, info in CATEGORY_PERFORMANCE.items() if info["priority"] == 1]

    for category in priority1_categories:
        if category not in UTTERANCE_TEMPLATES:
            print(f"[WARNING] {category}: 템플릿 없음, 건너뜀")
            continue

        templates = UTTERANCE_TEMPLATES[category]
        generated = []

        # 기본 템플릿 추가
        generated.extend(templates)

        # 각 템플릿에서 변형 생성
        for template in templates:
            variations = generate_template_variations(template, count=8)
            generated.extend(variations)

        # 목표 수량까지 채우기
        while len(generated) < target_count:
            template = random.choice(templates)
            variations = generate_template_variations(template, count=3)
            generated.extend(variations)

        # 중복 제거 후 목표 수량으로 제한
        generated = list(set(generated))[:target_count]
        augmented_data[category] = generated

        print(f"[OK] {category}: {len(generated)}개 생성")

    return augmented_data


# =============================================================================
# Step 2: Support<100 저성능 카테고리 보강
# =============================================================================

def generate_step2_data() -> Dict[str, List[str]]:
    """Step 2: Support<100 저성능 카테고리 + 고성능 카테고리 보강"""
    print("\n" + "=" * 60)
    print("[Step 2] Support<100 저성능 카테고리 + 고성능 카테고리 보강")
    print("=" * 60)

    augmented_data = {}
    target_count = 150  # 카테고리당 목표 추가 샘플 수

    # Priority 2 카테고리 + 템플릿이 있는 모든 카테고리
    all_template_categories = list(UTTERANCE_TEMPLATES.keys())

    for category in all_template_categories:
        # Priority 1은 Step 1에서 처리됨
        if category in CATEGORY_PERFORMANCE and CATEGORY_PERFORMANCE[category]["priority"] == 1:
            continue
        if category not in UTTERANCE_TEMPLATES:
            print(f"[WARNING] {category}: 템플릿 없음, 건너뜀")
            continue

        templates = UTTERANCE_TEMPLATES[category]
        generated = list(templates)

        # 변형 생성
        for template in templates:
            variations = generate_template_variations(template, count=8)
            generated.extend(variations)

        while len(generated) < target_count:
            template = random.choice(templates)
            variations = generate_template_variations(template, count=3)
            generated.extend(variations)

        generated = list(set(generated))[:target_count]
        augmented_data[category] = generated

        print(f"[OK] {category}: {len(generated)}개 생성")

    return augmented_data


# =============================================================================
# Step 3: LLM 기반 합성 데이터 생성
# =============================================================================

def generate_llm_synthetic_data(category: str, existing_samples: List[str], target_count: int = 50) -> List[str]:
    """OpenAI API를 사용하여 합성 데이터 생성"""
    try:
        from openai import OpenAI
        client = OpenAI()

        # 기존 샘플에서 예시 선택
        examples = random.sample(existing_samples, min(5, len(existing_samples)))
        examples_text = "\n".join([f"- {ex}" for ex in examples])

        prompt = f"""다음은 카드사 고객센터의 "{category}" 카테고리에 해당하는 고객 발화 예시입니다:

{examples_text}

위 예시를 참고하여 같은 카테고리에 해당하는 새로운 고객 발화 {target_count}개를 생성해주세요.

규칙:
1. 실제 고객이 말할 법한 자연스러운 구어체 사용
2. 다양한 말투와 표현 사용 (존댓말, 반말, 질문형, 요청형 등)
3. 같은 의미를 다르게 표현
4. 필러(어, 음, 저기요 등) 적절히 포함
5. 오타나 줄임말도 가끔 포함

JSON 배열 형식으로 반환:
["발화1", "발화2", ...]"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=2000,
        )

        content = response.choices[0].message.content

        # JSON 파싱
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            generated = json.loads(json_match.group())
            return generated[:target_count]

    except ImportError:
        print("[WARNING] OpenAI 패키지가 설치되지 않았습니다. LLM 생성을 건너뜁니다.")
    except Exception as e:
        print(f"[WARNING] LLM 생성 실패 ({category}): {e}")

    return []


def generate_step3_data(step1_data: Dict, step2_data: Dict) -> Dict[str, List[str]]:
    """Step 3: LLM 기반 합성 데이터 생성"""
    print("\n" + "=" * 60)
    print("[Step 3] LLM 기반 합성 데이터 생성")
    print("=" * 60)

    augmented_data = {}

    # 모든 기존 데이터 병합
    all_data = {}
    for cat, samples in step1_data.items():
        all_data[cat] = samples
    for cat, samples in step2_data.items():
        if cat in all_data:
            all_data[cat].extend(samples)
        else:
            all_data[cat] = samples

    # Priority 1, 2 카테고리에 대해 LLM 생성
    target_categories = [cat for cat, info in CATEGORY_PERFORMANCE.items() if info["priority"] in [1, 2]]

    for category in target_categories:
        if category not in all_data or len(all_data[category]) < 5:
            print(f"[WARNING] {category}: 기존 샘플 부족, 건너뜀")
            continue

        generated = generate_llm_synthetic_data(category, all_data[category], target_count=50)

        if generated:
            augmented_data[category] = generated
            print(f"[OK] {category}: {len(generated)}개 LLM 생성")
        else:
            print(f"[SKIP] {category}: LLM 생성 실패")

    return augmented_data


# =============================================================================
# Step 4: Back-translation 패러프레이징
# =============================================================================

def back_translate(text: str, source_lang: str = "ko", pivot_lang: str = "en") -> Optional[str]:
    """번역-역번역을 통한 패러프레이징"""
    try:
        from googletrans import Translator
        translator = Translator()

        # 한국어 -> 영어
        translated = translator.translate(text, src=source_lang, dest=pivot_lang)

        # 영어 -> 한국어
        back_translated = translator.translate(translated.text, src=pivot_lang, dest=source_lang)

        return back_translated.text

    except ImportError:
        return None
    except Exception:
        return None


def generate_step4_data(existing_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Step 4: Back-translation 패러프레이징"""
    print("\n" + "=" * 60)
    print("[Step 4] Back-translation 패러프레이징")
    print("=" * 60)

    augmented_data = {}

    try:
        from googletrans import Translator
    except ImportError:
        print("[WARNING] googletrans 패키지가 설치되지 않았습니다. 패러프레이징을 건너뜁니다.")
        return augmented_data

    for category, samples in existing_data.items():
        paraphrased = []

        # 샘플 중 일부 선택해서 패러프레이징
        selected_samples = random.sample(samples, min(30, len(samples)))

        for sample in selected_samples:
            try:
                result = back_translate(sample)
                if result and result != sample:
                    paraphrased.append(result)
            except Exception:
                continue

        if paraphrased:
            augmented_data[category] = paraphrased
            print(f"[OK] {category}: {len(paraphrased)}개 패러프레이징")

    return augmented_data


# =============================================================================
# Step 5: 데이터 밸런싱 및 전처리
# =============================================================================

def balance_and_preprocess(all_data: Dict[str, List[str]], target_per_category: int = 300) -> Dict[str, List[str]]:
    """데이터 밸런싱 및 전처리"""
    print("\n" + "=" * 60)
    print("[Step 5] 데이터 밸런싱 및 전처리")
    print("=" * 60)

    balanced_data = {}

    for category, samples in all_data.items():
        # 중복 제거
        unique_samples = list(set(samples))

        # 전처리
        processed = []
        for sample in unique_samples:
            # 공백 정리
            text = re.sub(r'\s+', ' ', sample).strip()
            # 너무 짧거나 긴 텍스트 제외
            if 3 <= len(text) <= 200:
                processed.append(text)

        # 오버샘플링/언더샘플링
        if len(processed) < target_per_category:
            # 오버샘플링
            while len(processed) < target_per_category:
                processed.append(random.choice(processed))
        else:
            # 언더샘플링
            processed = random.sample(processed, target_per_category)

        balanced_data[category] = processed
        print(f"[OK] {category}: {len(processed)}개 (원본 {len(unique_samples)}개)")

    return balanced_data


# =============================================================================
# 메인 실행
# =============================================================================

def save_augmented_data(data: Dict[str, List[str]], output_path: Path):
    """보강된 데이터 저장"""
    # JSON 형식으로 저장
    output = []
    for category, samples in data.items():
        for sample in samples:
            output.append({
                "text": sample,
                "intent": category,
                "intent_id": list(INTENT_CATEGORIES.keys())[list(INTENT_CATEGORIES.values()).index(category)]
            })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] 데이터 저장 완료: {output_path}")
    print(f"[OK] 총 샘플 수: {len(output):,}개")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Intent 분류 모델 학습 데이터 보강')
    parser.add_argument('--all', action='store_true', help='전체 데이터 보강 (Option D)')
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4, 5], help='특정 단계만 실행')
    parser.add_argument('--analyze', action='store_true', help='현재 데이터 분석만')
    parser.add_argument('--output', type=str, default='data/augmented_intent_training_data.json', help='출력 파일 경로')
    args = parser.parse_args()

    print("=" * 60)
    print("Intent 분류 모델 학습 데이터 보강 (Option D)")
    print("=" * 60)
    print(f"프로젝트 루트: {PROJECT_ROOT}")
    print(f"출력 경로: {args.output}")

    if args.analyze:
        print("\n[분석] 카테고리별 성능 현황:")
        for cat, info in sorted(CATEGORY_PERFORMANCE.items(), key=lambda x: x[1]["priority"]):
            print(f"  Priority {info['priority']}: {cat} (F1={info['f1']:.2f}, Support={info['support']})")
        return

    # 데이터 보강 실행
    all_data = defaultdict(list)

    # Step 1: F1=0 카테고리 템플릿 기반 생성
    if args.all or args.step == 1:
        step1_data = generate_step1_data()
        for cat, samples in step1_data.items():
            all_data[cat].extend(samples)

    # Step 2: Support<100 저성능 카테고리 보강
    if args.all or args.step == 2:
        step2_data = generate_step2_data()
        for cat, samples in step2_data.items():
            all_data[cat].extend(samples)

    # Step 3: LLM 기반 합성 데이터
    if args.all or args.step == 3:
        step3_data = generate_step3_data(
            dict(all_data) if all_data else {},
            {}
        )
        for cat, samples in step3_data.items():
            all_data[cat].extend(samples)

    # Step 4: Back-translation
    if args.all or args.step == 4:
        if all_data:
            step4_data = generate_step4_data(dict(all_data))
            for cat, samples in step4_data.items():
                all_data[cat].extend(samples)

    # Step 5: 밸런싱 및 전처리
    if args.all or args.step == 5:
        if all_data:
            all_data = balance_and_preprocess(dict(all_data))

    # 결과 저장
    if all_data:
        output_path = PROJECT_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_augmented_data(dict(all_data), output_path)

        print("\n" + "=" * 60)
        print("[완료] 데이터 보강 완료!")
        print("=" * 60)
        print(f"총 카테고리: {len(all_data)}개")
        print(f"총 샘플 수: {sum(len(v) for v in all_data.values()):,}개")
        print(f"저장 위치: {output_path}")
    else:
        print("\n[WARNING] 보강된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
