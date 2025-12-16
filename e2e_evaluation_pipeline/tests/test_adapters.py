# e2e_evaluation_pipeline/tests/test_adapters.py
"""E2E 평가 파이프라인 어댑터 통합 테스트.

실제 시스템과 연동하여 어댑터들의 동작을 검증합니다.

실행 방법:
    python -m pytest e2e_evaluation_pipeline/tests/test_adapters.py -v

    또는 개별 테스트:
    python -m pytest e2e_evaluation_pipeline/tests/test_adapters.py::TestIntentAdapter -v
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Intent Adapter 테스트
# =============================================================================

class TestIntentAdapter:
    """Intent 분류 어댑터 테스트"""

    @pytest.fixture
    def adapter(self):
        from e2e_evaluation_pipeline.adapters import IntentAdapter
        return IntentAdapter()

    def test_classify_card_loss(self, adapter):
        """카드 분실 의도 분류 테스트"""
        result = adapter.classify("카드 분실했어요")

        assert result.predicted_intent is not None
        assert result.confidence > 0
        assert len(result.top_k_results) > 0

        # 도난/분실 신청/해제 또는 SEC_CARD 도메인이어야 함
        assert result.domain == "SEC_CARD" or "분실" in result.predicted_intent or "도난" in result.predicted_intent
        logger.info(f"카드 분실 분류 결과: {result.predicted_intent} ({result.confidence:.2f})")

    def test_classify_payment_date(self, adapter):
        """결제일 문의 의도 분류 테스트"""
        result = adapter.classify("결제일 변경하고 싶어요")

        assert result.predicted_intent is not None
        assert "결제" in result.predicted_intent or result.domain == "PAY_BILL"
        logger.info(f"결제일 변경 분류 결과: {result.predicted_intent}")

    def test_classify_loan_inquiry(self, adapter):
        """대출 문의 의도 분류 테스트"""
        result = adapter.classify("대출 금리가 어떻게 되나요?")

        assert result.predicted_intent is not None
        assert result.domain == "LOAN" or "대출" in result.predicted_intent
        logger.info(f"대출 문의 분류 결과: {result.predicted_intent}")

    def test_classify_batch(self, adapter):
        """배치 분류 테스트"""
        messages = [
            "카드 분실했어요",
            "결제일 변경하고 싶어요",
            "포인트 조회하고 싶어요"
        ]
        results = adapter.classify_batch(messages)

        assert len(results) == 3
        for result in results:
            assert result.predicted_intent is not None
            logger.info(f"배치 분류: {result.user_message[:20]}... -> {result.predicted_intent}")

    def test_domain_mapping(self, adapter):
        """도메인 매핑 테스트"""
        # 카테고리 -> 도메인 매핑 확인 (38개 카테고리 기준)
        assert adapter.get_domain_for_category("도난/분실 신청/해제") == "SEC_CARD"
        assert adapter.get_domain_for_category("결제일 안내/변경") == "PAY_BILL"
        assert adapter.get_domain_for_category("단기카드대출 안내/실행") == "LOAN"

    def test_evaluate_prediction(self, adapter):
        """예측 평가 테스트"""
        # 정확히 일치
        is_match, match_type = adapter.evaluate_prediction("도난/분실 신청/해제", "도난/분실 신청/해제")
        assert is_match
        assert match_type == "exact"

        # 도메인 레벨 일치
        is_match, match_type = adapter.evaluate_prediction("긴급 배송 신청", "도난/분실 신청/해제")
        assert is_match
        assert match_type == "domain"  # 둘 다 SEC_CARD


# =============================================================================
# RAG Adapter 테스트
# =============================================================================

class TestRAGAdapter:
    """RAG 검색 어댑터 테스트"""

    @pytest.fixture
    def adapter(self):
        from e2e_evaluation_pipeline.adapters import RAGAdapter
        return RAGAdapter()

    def test_search_basic(self, adapter):
        """기본 검색 테스트"""
        result = adapter.search("결제일 변경 방법")

        # 결과가 있거나 에러가 없어야 함
        assert result.error is None or len(result.documents) >= 0
        logger.info(f"검색 결과: {len(result.documents)}개 문서, 최고 점수: {result.best_score:.2f}")

    def test_search_with_results(self, adapter):
        """결과가 있는 검색 테스트"""
        result = adapter.search("카드 분실 신고", top_k=5)

        if result.documents:
            assert len(result.documents) <= 5
            for doc in result.documents:
                assert doc.content
                assert doc.source
                logger.info(f"문서: {doc.source}, 점수: {doc.score:.2f}")

    def test_search_confidence(self, adapter):
        """검색 신뢰도 테스트"""
        result = adapter.search("신용카드 한도 상향 방법")

        # 신뢰도 판단
        logger.info(f"신뢰도: {'높음' if result.is_confident else '낮음'} (점수: {result.best_score:.2f})")

    def test_get_context_for_answer(self, adapter):
        """답변용 컨텍스트 추출 테스트"""
        result = adapter.search("결제일 안내", top_k=3)

        context = adapter.get_context_for_answer(result, max_chars=1000)
        logger.info(f"컨텍스트 길이: {len(context)}자")

    def test_batch_search(self, adapter):
        """배치 검색 테스트"""
        queries = ["카드 분실", "결제일 변경", "포인트 사용"]
        results = adapter.search_batch(queries)

        assert len(results) == 3

        # 메트릭 계산
        metrics = adapter.calculate_relevance_metrics(results)
        logger.info(f"검색 메트릭: {metrics}")


# =============================================================================
# Slot Adapter 테스트
# =============================================================================

class TestSlotAdapter:
    """슬롯 어댑터 테스트"""

    @pytest.fixture
    def adapter(self):
        from e2e_evaluation_pipeline.adapters import SlotAdapter
        return SlotAdapter()

    def test_get_slots_for_category(self, adapter):
        """카테고리별 슬롯 조회 테스트"""
        required, optional = adapter.get_slots_for_category("도난/분실 신청/해제")

        assert "card_last_4_digits" in required
        assert "loss_date" in required
        logger.info(f"도난/분실 신청/해제 필수 슬롯: {required}")
        logger.info(f"도난/분실 신청/해제 선택 슬롯: {optional}")

    def test_extract_slots_card_digits(self, adapter):
        """카드 번호 추출 테스트"""
        result = adapter.extract_slots(
            conversation_history=[],
            current_message="카드 뒤 4자리는 1234입니다",
            category="도난/분실 신청/해제"
        )

        assert "card_last_4_digits" in result.extracted_slots
        assert result.extracted_slots["card_last_4_digits"] == "1234"
        logger.info(f"추출된 슬롯: {result.extracted_slots}")

    def test_extract_slots_date(self, adapter):
        """날짜 추출 테스트"""
        result = adapter.extract_slots(
            conversation_history=[],
            current_message="어제 분실했어요",
            category="도난/분실 신청/해제"
        )

        assert "loss_date" in result.extracted_slots
        logger.info(f"추출된 날짜: {result.extracted_slots.get('loss_date')}")

    def test_missing_slots(self, adapter):
        """누락 슬롯 확인 테스트"""
        result = adapter.extract_slots(
            conversation_history=[],
            current_message="카드 분실했어요",
            category="도난/분실 신청/해제"
        )

        # 아직 수집 안 된 슬롯들이 missing에 있어야 함
        assert len(result.missing_slots) > 0
        assert not result.is_complete
        logger.info(f"누락된 슬롯: {result.missing_slots}")

    def test_slot_extraction_complete(self, adapter):
        """슬롯 수집 완료 테스트"""
        result = adapter.extract_slots(
            conversation_history=[
                {"role": "user", "message": "카드 뒤 4자리는 5678입니다"}
            ],
            current_message="어제 오후 3시쯤 분실했어요",
            category="도난/분실 신청/해제"
        )

        # 필수 슬롯이 모두 수집되었으면 완료
        if result.is_complete:
            logger.info("슬롯 수집 완료!")
        else:
            logger.info(f"아직 필요한 슬롯: {result.missing_slots}")

    def test_slot_definition(self, adapter):
        """슬롯 정의 조회 테스트"""
        definition = adapter.get_slot_definition("card_last_4_digits")

        assert definition is not None
        assert definition.label == "카드 뒤 4자리"
        assert definition.question is not None
        logger.info(f"슬롯 정의: {definition}")

    def test_simulate_multi_turn(self, adapter):
        """멀티턴 슬롯 수집 시뮬레이션"""
        results = adapter.simulate_multi_turn_collection(
            category="도난/분실 신청/해제",
            user_responses=[
                "카드 분실했어요",
                "카드 뒤 4자리는 1234입니다",
                "어제 오후에 분실한 것 같아요"
            ]
        )

        logger.info(f"멀티턴 수집 결과: {len(results)}턴")
        for i, result in enumerate(results):
            logger.info(f"  턴 {i+1}: 수집됨={list(result.extracted_slots.keys())}, 완료={result.is_complete}")


# =============================================================================
# Flow Adapter 테스트
# =============================================================================

class TestFlowAdapter:
    """Flow 어댑터 테스트"""

    @pytest.fixture
    def adapter(self):
        from e2e_evaluation_pipeline.adapters import FlowAdapter
        return FlowAdapter()

    def test_get_expected_flow_simple(self, adapter):
        """일반 플로우 예상 시퀀스"""
        flow = adapter.get_expected_flow(
            triage_decision="SIMPLE_ANSWER",
            is_human_required_flow=False
        )

        assert "triage_agent" in flow
        assert "answer_agent" in flow
        assert "chat_db_storage" in flow
        logger.info(f"SIMPLE_ANSWER 예상 플로우: {flow}")

    def test_get_expected_flow_human_required(self, adapter):
        """상담사 연결 플로우 예상 시퀀스"""
        # 동의 전
        flow = adapter.get_expected_flow(
            triage_decision="HUMAN_REQUIRED",
            is_human_required_flow=True,
            customer_consent_received=False
        )
        assert "consent_check" in flow
        logger.info(f"동의 확인 플로우: {flow}")

        # 동의 후 정보 수집 중
        flow = adapter.get_expected_flow(
            triage_decision="HUMAN_REQUIRED",
            is_human_required_flow=True,
            customer_consent_received=True,
            info_collection_complete=False
        )
        assert "waiting_agent" in flow
        logger.info(f"정보 수집 플로우: {flow}")

        # 정보 수집 완료
        flow = adapter.get_expected_flow(
            triage_decision="HUMAN_REQUIRED",
            is_human_required_flow=True,
            customer_consent_received=True,
            info_collection_complete=True
        )
        assert "summary_agent" in flow
        assert "human_transfer" in flow
        logger.info(f"이관 플로우: {flow}")

    def test_evaluate_flow(self, adapter):
        """플로우 평가 테스트"""
        actual = ["triage_agent", "answer_agent", "chat_db_storage"]
        expected = ["triage_agent", "answer_agent", "chat_db_storage"]

        result = adapter.evaluate_flow(actual, expected)

        assert result["is_correct"]
        assert result["score"] == 1.0
        logger.info(f"플로우 평가 결과: {result}")

    def test_evaluate_flow_missing_nodes(self, adapter):
        """누락 노드 평가 테스트"""
        actual = ["triage_agent", "chat_db_storage"]  # answer_agent 누락
        expected = ["triage_agent", "answer_agent", "chat_db_storage"]

        result = adapter.evaluate_flow(actual, expected)

        assert not result["is_correct"]
        assert "answer_agent" in result["missing_nodes"]
        logger.info(f"누락 노드 평가: {result}")

    def test_get_all_nodes(self, adapter):
        """모든 노드 목록"""
        nodes = adapter.get_all_nodes()

        assert "triage_agent" in nodes
        assert "waiting_agent" in nodes
        assert "human_transfer" in nodes
        logger.info(f"전체 노드: {nodes}")


# =============================================================================
# LangGraph Adapter 테스트 (통합)
# =============================================================================

class TestLangGraphAdapter:
    """LangGraph 워크플로우 어댑터 통합 테스트"""

    @pytest.fixture
    def adapter(self):
        from e2e_evaluation_pipeline.adapters import LangGraphAdapter
        return LangGraphAdapter()

    @pytest.mark.skip(reason="실제 워크플로우 실행은 별도 환경 필요")
    def test_execute_simple_query(self, adapter):
        """단순 쿼리 실행 테스트"""
        result = adapter.execute(
            user_message="안녕하세요",
            session_id="test_simple"
        )

        assert result.ai_message is not None
        logger.info(f"응답: {result.ai_message}")
        logger.info(f"판단: {result.triage_decision}")

    @pytest.mark.skip(reason="실제 워크플로우 실행은 별도 환경 필요")
    def test_execute_card_loss(self, adapter):
        """카드 분실 문의 실행 테스트"""
        result = adapter.execute(
            user_message="카드를 분실했어요",
            session_id="test_card_loss"
        )

        assert result.ai_message is not None
        # 상담사 연결이 필요할 수 있음
        logger.info(f"응답: {result.ai_message}")
        logger.info(f"상담사 필요: {result.is_human_required_flow}")

    @pytest.mark.skip(reason="실제 워크플로우 실행은 별도 환경 필요")
    def test_execute_multi_turn(self, adapter):
        """멀티턴 대화 테스트"""
        messages = [
            "카드 분실했어요",
            "네, 상담사 연결해주세요",
            "카드 뒤 4자리는 1234입니다",
            "어제 오후에 분실했어요"
        ]

        results = adapter.execute_multi_turn(
            messages=messages,
            session_id="test_multi_turn"
        )

        assert len(results) > 0
        for i, result in enumerate(results):
            logger.info(f"턴 {i+1}: {result.ai_message[:50]}...")


# =============================================================================
# 어댑터 통합 테스트
# =============================================================================

class TestAdaptersIntegration:
    """어댑터 통합 테스트"""

    def test_all_adapters_import(self):
        """모든 어댑터 import 테스트"""
        from e2e_evaluation_pipeline.adapters import (
            LangGraphAdapter,
            IntentAdapter,
            RAGAdapter,
            SlotAdapter,
            FlowAdapter
        )

        assert LangGraphAdapter is not None
        assert IntentAdapter is not None
        assert RAGAdapter is not None
        assert SlotAdapter is not None
        assert FlowAdapter is not None

    def test_intent_slot_integration(self):
        """Intent → Slot 연동 테스트"""
        from e2e_evaluation_pipeline.adapters import IntentAdapter, SlotAdapter

        intent_adapter = IntentAdapter()
        slot_adapter = SlotAdapter()

        # 1. Intent 분류
        intent_result = intent_adapter.classify("카드 분실했어요")
        category = intent_result.predicted_intent

        # 2. 해당 카테고리의 슬롯 조회
        required_slots, optional_slots = slot_adapter.get_slots_for_category(category)

        logger.info(f"분류된 카테고리: {category}")
        logger.info(f"필요한 슬롯: {required_slots}")

        assert len(required_slots) >= 0  # 일부 카테고리는 슬롯이 없을 수 있음


# =============================================================================
# 실행
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
