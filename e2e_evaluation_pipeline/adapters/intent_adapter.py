# e2e_evaluation_pipeline/adapters/intent_adapter.py
"""Intent 분류 모듈과 E2E 평가 파이프라인 연동 어댑터.

실제 triage_agent의 intent_classification_tool을 호출하여
의도 분류 결과를 평가 가능한 형태로 변환합니다.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntentClassificationResult:
    """의도 분류 결과"""
    user_message: str
    predicted_intent: str
    confidence: float
    top_k_results: List[Dict[str, Any]]
    domain: Optional[str] = None
    error: Optional[str] = None


# 38개 카테고리 → 8개 도메인 매핑 (slot_definitions.json 기준)
CATEGORY_TO_DOMAIN = {
    # SEC_CARD (인증/보안/카드관리)
    "도난/분실 신청/해제": "SEC_CARD",
    "긴급 배송 신청": "SEC_CARD",
    "기타": "SEC_CARD",

    # LIMIT_AUTH (한도/승인)
    "한도 안내": "LIMIT_AUTH",
    "한도상향 접수/처리": "LIMIT_AUTH",
    "승인취소/매출취소 안내": "LIMIT_AUTH",
    "심사 진행사항 안내": "LIMIT_AUTH",
    "신용공여기간 안내": "LIMIT_AUTH",

    # PAY_BILL (결제/청구)
    "가상계좌 안내": "PAY_BILL",
    "가상계좌 예약/취소": "PAY_BILL",
    "결제계좌 안내/변경": "PAY_BILL",
    "결제대금 안내": "PAY_BILL",
    "결제일 안내/변경": "PAY_BILL",
    "입금내역 안내": "PAY_BILL",
    "이용내역 안내": "PAY_BILL",
    "이용방법 안내": "PAY_BILL",
    "청구지 안내/변경": "PAY_BILL",
    "쇼핑케어": "PAY_BILL",
    "매출구분 변경": "PAY_BILL",

    # DELINQ (연체/수납)
    "연체대금 안내": "DELINQ",
    "연체대금 즉시출금": "DELINQ",
    "선결제/즉시출금": "DELINQ",
    "일부결제대금이월약정 안내": "DELINQ",
    "일부결제대금이월약정 해지": "DELINQ",

    # LOAN (대출)
    "단기카드대출 안내/실행": "LOAN",
    "장기카드대출 안내": "LOAN",
    "오토할부/오토캐쉬백 안내/신청/취소": "LOAN",

    # BENEFIT (포인트/혜택/바우처)
    "포인트/마일리지 안내": "BENEFIT",
    "포인트/마일리지 전환등록": "BENEFIT",
    "정부지원 바우처 (등유, 임신 등)": "BENEFIT",
    "프리미엄 바우처 안내/발급": "BENEFIT",
    "이벤트 안내": "BENEFIT",
    "연회비 안내": "BENEFIT",

    # DOC_TAX (증명/세금)
    "증명서/확인서 발급": "DOC_TAX",
    "교육비": "DOC_TAX",
    "금리인하요구권 안내/신청": "DOC_TAX",

    # UTILITY (공과금)
    "도시가스": "UTILITY",
    "전화요금": "UTILITY",

    # _DEFAULT (기타)
    "기타 문의": "_DEFAULT",
}

# 도메인 한글명 매핑 (slot_definitions.json 기준)
DOMAIN_NAMES = {
    "SEC_CARD": "인증/보안/카드관리",
    "LIMIT_AUTH": "한도/승인",
    "PAY_BILL": "결제/청구",
    "DELINQ": "연체/수납",
    "LOAN": "대출",
    "BENEFIT": "포인트/혜택/바우처",
    "UTILITY": "공과금",
    "DOC_TAX": "증명/세금",
    "_DEFAULT": "기타"
}


class IntentAdapter:
    """Intent 분류 어댑터.

    E2E 평가 파이프라인에서 실제 Intent 분류 모델을 호출하고
    결과를 평가 가능한 형태로 변환합니다.
    """

    def __init__(self):
        self._classifier = None
        self._initialized = False

    def _ensure_initialized(self):
        """분류기 지연 초기화"""
        if self._initialized:
            return

        try:
            from ai_engine.graph.tools.intent_classification_tool import _get_classifier
            self._classifier = _get_classifier()
            if self._classifier is None:
                raise RuntimeError("Intent 분류 모델 로드 실패")
            self._initialized = True
            logger.info("Intent 분류 모델 초기화 완료")
        except Exception as e:
            logger.error(f"Intent 분류 모델 초기화 실패: {e}")
            raise RuntimeError(f"Intent 분류 모델 초기화 실패: {e}")

    def classify(
        self,
        user_message: str,
        top_k: int = 3
    ) -> IntentClassificationResult:
        """의도 분류 수행.

        Args:
            user_message: 사용자 메시지
            top_k: 상위 K개 결과 반환

        Returns:
            IntentClassificationResult: 분류 결과
        """
        self._ensure_initialized()

        try:
            # 모델 호출
            results = self._classifier.predict(user_message, top_k=top_k)

            if not results:
                return IntentClassificationResult(
                    user_message=user_message,
                    predicted_intent="기타",
                    confidence=0.0,
                    top_k_results=[],
                    error="분류 결과 없음"
                )

            # 최상위 결과
            top_result = results[0]
            predicted_intent = top_result.get("intent", "기타")
            confidence = top_result.get("confidence", 0.0)

            # 도메인 매핑
            domain = CATEGORY_TO_DOMAIN.get(predicted_intent)

            return IntentClassificationResult(
                user_message=user_message,
                predicted_intent=predicted_intent,
                confidence=confidence,
                top_k_results=results,
                domain=domain
            )

        except Exception as e:
            logger.error(f"Intent 분류 오류: {e}", exc_info=True)
            return IntentClassificationResult(
                user_message=user_message,
                predicted_intent="기타",
                confidence=0.0,
                top_k_results=[],
                error=str(e)
            )

    def classify_batch(
        self,
        messages: List[str],
        top_k: int = 3
    ) -> List[IntentClassificationResult]:
        """배치 의도 분류.

        Args:
            messages: 사용자 메시지 리스트
            top_k: 각 메시지별 상위 K개 결과

        Returns:
            List[IntentClassificationResult]: 분류 결과 리스트
        """
        results = []
        for msg in messages:
            result = self.classify(msg, top_k=top_k)
            results.append(result)
        return results

    def get_domain_for_category(self, category: str) -> Optional[str]:
        """카테고리에 해당하는 도메인 반환.

        Args:
            category: 38개 카테고리 중 하나

        Returns:
            도메인 코드 또는 None
        """
        return CATEGORY_TO_DOMAIN.get(category)

    def get_domain_name(self, domain_code: str) -> str:
        """도메인 코드의 한글명 반환.

        Args:
            domain_code: 도메인 코드 (예: SEC_CARD)

        Returns:
            도메인 한글명 (예: 분실/보안)
        """
        return DOMAIN_NAMES.get(domain_code, "기타")

    def evaluate_prediction(
        self,
        predicted: str,
        expected: str,
        allow_domain_match: bool = True
    ) -> Tuple[bool, str]:
        """예측 결과 평가.

        Args:
            predicted: 예측된 카테고리
            expected: 기대 카테고리
            allow_domain_match: 도메인 레벨 일치도 허용할지 여부

        Returns:
            (일치 여부, 일치 유형)
            일치 유형: "exact", "domain", "none"
        """
        # 정확히 일치
        if predicted == expected:
            return True, "exact"

        # 도메인 레벨 일치 확인
        if allow_domain_match:
            pred_domain = self.get_domain_for_category(predicted)
            exp_domain = self.get_domain_for_category(expected)

            if pred_domain and exp_domain and pred_domain == exp_domain:
                return True, "domain"

        return False, "none"

    def get_all_categories(self) -> List[str]:
        """모든 카테고리 목록 반환."""
        return list(CATEGORY_TO_DOMAIN.keys())

    def get_all_domains(self) -> List[str]:
        """모든 도메인 코드 목록 반환."""
        return list(DOMAIN_NAMES.keys())
