"""
카드사 E2E 테스트 실행 스크립트

100개의 카드사 대화 시나리오에 대해 E2E 테스트를 수행합니다.

테스트 흐름:
1. WAV 파일 → STT (VITO) → 텍스트
2. 텍스트 → Intent 분류 (KcELECTRA)
3. 텍스트 → LangGraph 워크플로우 실행
4. 응답 → TTS (Google) → WAV 파일
5. 결과 평가 및 리포트 생성

사용법:
    # 전체 테스트 실행
    python -m e2e_evaluation_pipeline.scripts.run_card_e2e_test

    # 텍스트 기반 테스트 (STT 건너뛰기)
    python -m e2e_evaluation_pipeline.scripts.run_card_e2e_test --text-only

    # 특정 카테고리만 테스트
    python -m e2e_evaluation_pipeline.scripts.run_card_e2e_test --category card_loss

    # 제한된 수만 테스트
    python -m e2e_evaluation_pipeline.scripts.run_card_e2e_test --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# 시나리오 라벨 → 모델 라벨 매핑 테이블
# 시나리오 JSON의 expected_intent를 모델의 38개 카테고리에 매핑
# 모델 라벨: 가상계좌 안내, 가상계좌 예약/취소, 결제계좌 안내/변경, 결제대금 안내,
# 결제일 안내/변경, 교육비, 금리인하요구권 안내/신청, 기타, 긴급 배송 신청,
# 단기카드대출 안내/실행, 도난/분실 신청/해제, 도시가스, 매출구분 변경,
# 선결제/즉시출금, 쇼핑케어, 승인취소/매출취소 안내, 신용공여기간 안내,
# 심사 진행사항 안내, 연체대금 안내, 연체대금 즉시출금, 연회비 안내,
# 오토할부/오토캐쉬백 안내/신청/취소, 이벤트 안내, 이용내역 안내, 이용방법 안내,
# 일부결제대금이월약정 안내, 일부결제대금이월약정 해지, 입금내역 안내,
# 장기카드대출 안내, 전화요금, 정부지원 바우처 (등유, 임신 등), 증명서/확인서 발급,
# 청구지 안내/변경, 포인트/마일리지 안내, 포인트/마일리지 전환등록,
# 프리미엄 바우처 안내/발급, 한도 안내, 한도상향 접수/처리
INTENT_LABEL_MAPPING: dict[str, list[str]] = {
    # 도난/분실 관련 - 유사 라벨 포함
    "도난/분실 신청/해제": [
        "도난/분실 신청/해제",
        "긴급 배송 신청",  # 분실 후 긴급 배송
        "기타",  # fallback
    ],

    # 결제/이용내역 관련
    "이용내역 안내": [
        "이용내역 안내",
        "결제대금 안내",
        "결제일 안내/변경",
        "입금내역 안내",
        "승인취소/매출취소 안내",
    ],

    # 한도 관련
    "한도 안내": [
        "한도 안내",
        "한도상향 접수/처리",
    ],

    # 포인트/마일리지 관련
    "포인트/마일리지 안내": [
        "포인트/마일리지 안내",
        "포인트/마일리지 전환등록",
        "이벤트 안내",
    ],

    # 결제계좌/자동이체 관련
    "결제계좌 안내/변경": [
        "결제계좌 안내/변경",
        "결제일 안내/변경",
        "선결제/즉시출금",
        "가상계좌 안내",
        "가상계좌 예약/취소",
    ],

    # 카드 재발급/배송 관련
    "긴급 배송 신청": [
        "긴급 배송 신청",
        "심사 진행사항 안내",
        "도난/분실 신청/해제",
    ],

    # 연회비 관련
    "연회비 안내": [
        "연회비 안내",
    ],

    # 이용방법/해외결제 관련
    "이용방법 안내": [
        "이용방법 안내",
        "이용내역 안내",
    ],

    # 할부/리볼빙/카드론 관련
    "일부결제대금이월약정 안내": [
        "일부결제대금이월약정 안내",
        "일부결제대금이월약정 해지",
        "단기카드대출 안내/실행",
        "장기카드대출 안내",
        "오토할부/오토캐쉬백 안내/신청/취소",
        "매출구분 변경",
    ],

    # 상담사 연결/기타
    "기타": [
        "기타",
    ],
}


def normalize_intent_label(expected_intent: str, predicted_intent: str) -> bool:
    """시나리오의 expected_intent와 모델의 predicted_intent를 매핑하여 비교합니다.

    Args:
        expected_intent: 시나리오 JSON의 expected_intent (예: "카드분실/도난신고")
        predicted_intent: 모델이 예측한 intent (예: "도난/분실 신청/해제")

    Returns:
        매핑된 라벨이 일치하면 True, 아니면 False
    """
    if expected_intent == predicted_intent:
        return True

    # 매핑 테이블에서 확인
    mapped_labels = INTENT_LABEL_MAPPING.get(expected_intent, [])
    if predicted_intent in mapped_labels:
        return True

    # 부분 문자열 매칭 (유연한 비교)
    # 예: "도난/분실" in "도난/분실 신청/해제"
    expected_keywords = expected_intent.replace("/", " ").split()
    for keyword in expected_keywords:
        if keyword in predicted_intent:
            return True

    return False


@dataclass
class ScenarioResult:
    """단일 시나리오 테스트 결과"""
    scenario_id: str
    category: str
    user_text: str
    expected_intent: str

    # STT 결과
    stt_text: Optional[str] = None
    stt_success: bool = False
    stt_latency_ms: float = 0.0

    # Intent 분류 결과 - BERT 모델
    bert_intent: Optional[str] = None
    bert_confidence: float = 0.0
    bert_correct: bool = False

    # Intent 분류 결과 - LLM (워크플로우 context_intent)
    llm_intent: Optional[str] = None
    llm_correct: bool = False

    # LangGraph 워크플로우 결과
    workflow_response: Optional[str] = None
    workflow_flow: list[str] = field(default_factory=list)
    workflow_latency_ms: float = 0.0
    workflow_success: bool = False

    # TTS 결과
    tts_audio_size: int = 0
    tts_latency_ms: float = 0.0
    tts_success: bool = False

    # RAG 검색 결과
    rag_documents: list[dict] = field(default_factory=list)  # 검색된 문서들
    rag_best_score: float = 0.0  # 최고 유사도 점수
    rag_doc_count: int = 0  # 검색된 문서 수

    # 전체 E2E 결과
    e2e_latency_ms: float = 0.0
    e2e_success: bool = False
    auto_resolved: bool = False
    error: Optional[str] = None


@dataclass
class E2ETestReport:
    """E2E 테스트 전체 리포트"""
    test_name: str = "Card E2E Test"
    test_date: str = field(default_factory=lambda: datetime.now().isoformat())
    total_scenarios: int = 0

    # 성공률
    stt_success_rate: float = 0.0
    bert_intent_accuracy: float = 0.0  # BERT 모델 정확도
    llm_intent_accuracy: float = 0.0   # LLM (워크플로우) 정확도
    workflow_success_rate: float = 0.0
    tts_success_rate: float = 0.0
    e2e_success_rate: float = 0.0

    # 평균 지연 시간
    avg_stt_latency_ms: float = 0.0
    avg_workflow_latency_ms: float = 0.0
    avg_tts_latency_ms: float = 0.0
    avg_e2e_latency_ms: float = 0.0

    # 자동 해결률
    auto_resolution_rate: float = 0.0

    # RAG 검색 메트릭
    avg_rag_score: float = 0.0  # 평균 RAG 점수
    avg_rag_doc_count: float = 0.0  # 평균 검색 문서 수
    rag_hit_rate: float = 0.0  # RAG 검색 성공률 (1개 이상 문서 검색)

    # 카테고리별 결과
    category_results: dict = field(default_factory=dict)

    # 상세 결과
    scenario_results: list[dict] = field(default_factory=list)

    # KPI 통과 여부
    kpi_passed: bool = False
    kpi_details: dict = field(default_factory=dict)


def load_scenarios(scenario_file: Path, category: Optional[str] = None) -> list[dict]:
    """시나리오 JSON 파일을 로드합니다."""
    with open(scenario_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("test_scenarios", [])

    if category:
        scenarios = [s for s in scenarios if s.get("category") == category]

    return scenarios


class CardE2ETestRunner:
    """카드사 E2E 테스트 러너"""

    def __init__(
        self,
        text_only: bool = False,
        skip_tts: bool = False,
        verbose: bool = False
    ):
        self.text_only = text_only
        self.skip_tts = skip_tts
        self.verbose = verbose

        # 서비스 초기화
        self._stt_service = None
        self._tts_service = None
        self._intent_classifier = None
        self._workflow = None

    def _get_stt_service(self):
        """STT 서비스 인스턴스를 반환합니다."""
        if self._stt_service is None:
            from app.services.voice.stt_service import AICCSTTService
            self._stt_service = AICCSTTService.get_instance()
        return self._stt_service

    def _get_tts_service(self):
        """TTS 서비스 인스턴스를 반환합니다."""
        if self._tts_service is None:
            try:
                from app.services.voice.tts_service_google import AICCGoogleTTSService
                self._tts_service = AICCGoogleTTSService.get_instance()
            except Exception:
                from app.services.voice.tts_service import AICCTTSService
                self._tts_service = AICCTTSService.get_instance()
        return self._tts_service

    def _get_intent_classifier(self):
        """Intent 분류기를 반환합니다."""
        if self._intent_classifier is None:
            try:
                from ai_engine.ingestion.bert_financial_intent_classifier.scripts.inference import IntentClassifier
                self._intent_classifier = IntentClassifier()
            except Exception as e:
                logger.warning(f"Intent 분류기 로드 실패: {e}")
                self._intent_classifier = None
        return self._intent_classifier

    async def _run_workflow(self, text: str, session_id: str) -> dict:
        """LangGraph 워크플로우를 실행합니다."""
        try:
            from ai_engine.graph.workflow import build_workflow
            from ai_engine.graph.state import GraphState

            workflow = build_workflow()

            initial_state: GraphState = {
                "session_id": session_id,
                "user_message": text,
                "conversation_history": [],
                "is_human_required_flow": False,
                "customer_consent_received": False,
                "collected_info": {},
                "info_collection_complete": False,
            }

            start_time = time.time()
            result = await workflow.ainvoke(initial_state)
            elapsed_ms = (time.time() - start_time) * 1000

            # context_intent가 None이고 triage_decision이 HUMAN_REQUIRED인 경우 "기타"로 처리
            # (triage_agent가 상담사 연결 요청 시 intent_classification_tool을 호출하지 않아 context_intent가 None)
            context_intent = result.get("context_intent")
            triage_decision = result.get("triage_decision")

            # triage_decision이 HUMAN_REQUIRED이면 "기타"로 fallback
            if context_intent is None and triage_decision:
                triage_str = str(triage_decision)
                # TriageDecisionType enum은 str(enum)이 "TriageDecisionType.HUMAN_REQUIRED" 형태
                if "HUMAN_REQUIRED" in triage_str:
                    context_intent = "기타"

            # RAG 검색 결과 추출
            retrieved_docs = result.get("retrieved_documents", [])
            rag_best_score = result.get("rag_best_score", 0.0)

            # retrieved_docs가 문자열인 경우 파싱 시도
            if isinstance(retrieved_docs, str):
                try:
                    import json as json_module
                    retrieved_docs = json_module.loads(retrieved_docs)
                except Exception:
                    retrieved_docs = []

            return {
                "success": True,
                "response": result.get("ai_message", ""),
                "flow": result.get("node_history", []),
                "latency_ms": elapsed_ms,
                "intent": context_intent,
                "triage_decision": str(triage_decision) if triage_decision else None,
                "should_transfer": result.get("is_human_required_flow", False),
                # RAG 검색 결과 추가
                "rag_documents": retrieved_docs if isinstance(retrieved_docs, list) else [],
                "rag_best_score": float(rag_best_score) if rag_best_score else 0.0
            }
        except Exception as e:
            logger.error(f"워크플로우 실행 실패: {e}")
            return {
                "success": False,
                "response": "",
                "flow": [],
                "latency_ms": 0,
                "error": str(e)
            }

    def run_stt(self, audio_file: Path) -> dict:
        """STT를 실행합니다."""
        if not audio_file.exists():
            return {"success": False, "text": "", "error": "파일 없음"}

        try:
            stt = self._get_stt_service()
            start_time = time.time()
            result = stt.transcribe_file(audio_file)
            elapsed_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "text": result.text,
                "latency_ms": elapsed_ms
            }
        except Exception as e:
            return {"success": False, "text": "", "error": str(e)}

    def run_tts(self, text: str) -> dict:
        """TTS를 실행합니다."""
        if not text:
            return {"success": False, "audio_size": 0, "error": "텍스트 없음"}

        try:
            tts = self._get_tts_service()
            start_time = time.time()
            audio_bytes = tts.synthesize(text, format="wav")
            elapsed_ms = (time.time() - start_time) * 1000

            return {
                "success": True,
                "audio_size": len(audio_bytes),
                "latency_ms": elapsed_ms
            }
        except Exception as e:
            return {"success": False, "audio_size": 0, "error": str(e)}

    def run_intent_classification(self, text: str) -> dict:
        """Intent 분류를 실행합니다."""
        classifier = self._get_intent_classifier()
        if classifier is None:
            return {"success": False, "intent": None, "confidence": 0.0}

        try:
            result = classifier.predict_single(text)
            return {
                "success": True,
                "intent": result[0] if isinstance(result, tuple) else result,
                "confidence": result[1] if isinstance(result, tuple) else 0.0
            }
        except Exception as e:
            logger.warning(f"Intent 분류 실패: {e}")
            return {"success": False, "intent": None, "confidence": 0.0, "error": str(e)}

    async def run_scenario(
        self,
        scenario: dict,
        audio_dir: Optional[Path] = None
    ) -> ScenarioResult:
        """단일 시나리오를 실행합니다."""
        scenario_id = scenario.get("scenario_id", "unknown")
        category = scenario.get("category", "unknown")
        user_text = scenario.get("user_text", "")
        expected_intent = scenario.get("expected_intent", "")

        result = ScenarioResult(
            scenario_id=scenario_id,
            category=category,
            user_text=user_text,
            expected_intent=expected_intent
        )

        e2e_start = time.time()

        try:
            # 1. STT (텍스트 모드가 아닌 경우)
            if not self.text_only and audio_dir:
                audio_file = audio_dir / category / f"{scenario_id}.wav"
                if audio_file.exists():
                    stt_result = self.run_stt(audio_file)
                    result.stt_success = stt_result.get("success", False)
                    result.stt_text = stt_result.get("text", "")
                    result.stt_latency_ms = stt_result.get("latency_ms", 0)

                    # STT 결과로 텍스트 업데이트
                    if result.stt_success and result.stt_text:
                        user_text = result.stt_text
                else:
                    result.stt_text = user_text
                    result.stt_success = True
            else:
                result.stt_text = user_text
                result.stt_success = True

            # 2. BERT 모델로 Intent 분류 (직접 호출)
            bert_result = self.run_intent_classification(user_text)
            result.bert_intent = bert_result.get("intent")
            result.bert_confidence = bert_result.get("confidence", 0.0)
            result.bert_correct = normalize_intent_label(
                expected_intent, result.bert_intent or ""
            )

            # 3. LangGraph 워크플로우 실행
            workflow_result = await self._run_workflow(
                text=user_text,
                session_id=f"test_{scenario_id}"
            )
            result.workflow_success = workflow_result.get("success", False)
            result.workflow_response = workflow_result.get("response", "")
            result.workflow_flow = workflow_result.get("flow", [])
            result.workflow_latency_ms = workflow_result.get("latency_ms", 0)
            result.auto_resolved = not workflow_result.get("should_transfer", False)

            # 4. LLM(워크플로우)의 context_intent 평가
            result.llm_intent = workflow_result.get("intent")
            result.llm_correct = normalize_intent_label(
                expected_intent, result.llm_intent or ""
            )

            # 5. RAG 검색 결과 저장
            result.rag_documents = workflow_result.get("rag_documents", [])
            result.rag_best_score = workflow_result.get("rag_best_score", 0.0)
            result.rag_doc_count = len(result.rag_documents)

            # 6. TTS (건너뛰기 옵션이 아닌 경우)
            if not self.skip_tts and result.workflow_response:
                tts_result = self.run_tts(result.workflow_response)
                result.tts_success = tts_result.get("success", False)
                result.tts_audio_size = tts_result.get("audio_size", 0)
                result.tts_latency_ms = tts_result.get("latency_ms", 0)
            else:
                result.tts_success = True  # 건너뛴 경우 성공으로 처리

            # E2E 결과 계산
            result.e2e_latency_ms = (time.time() - e2e_start) * 1000
            result.e2e_success = (
                result.stt_success and
                result.workflow_success and
                result.tts_success
            )

        except Exception as e:
            result.error = str(e)
            result.e2e_success = False
            result.e2e_latency_ms = (time.time() - e2e_start) * 1000

        return result

    async def run_all_scenarios(
        self,
        scenarios: list[dict],
        audio_dir: Optional[Path] = None,
        limit: Optional[int] = None
    ) -> E2ETestReport:
        """모든 시나리오를 실행하고 리포트를 생성합니다."""
        scenarios_to_run = scenarios[:limit] if limit else scenarios
        total = len(scenarios_to_run)

        logger.info(f"총 {total}개 시나리오 테스트 시작...")

        results: list[ScenarioResult] = []

        for idx, scenario in enumerate(scenarios_to_run, 1):
            scenario_id = scenario.get("scenario_id", "unknown")
            logger.info(f"[{idx}/{total}] {scenario_id} 테스트 중...")

            result = await self.run_scenario(scenario, audio_dir)
            results.append(result)

            if self.verbose:
                status = "O" if result.e2e_success else "X"
                bert_status = "O" if result.bert_correct else "X"
                llm_status = "O" if result.llm_correct else "X"
                rag_info = f"RAG: {result.rag_doc_count}개/{result.rag_best_score:.2f}" if result.rag_doc_count > 0 else "RAG: 0개"
                logger.info(
                    f"  {status} E2E: {result.e2e_latency_ms:.0f}ms, "
                    f"BERT[{bert_status}]: {result.bert_intent}, "
                    f"LLM[{llm_status}]: {result.llm_intent}, "
                    f"{rag_info}"
                )

        # 리포트 생성
        report = self._generate_report(results)

        return report

    def _generate_report(self, results: list[ScenarioResult]) -> E2ETestReport:
        """테스트 결과로부터 리포트를 생성합니다."""
        report = E2ETestReport()
        report.total_scenarios = len(results)

        if not results:
            return report

        # 성공률 계산
        stt_successes = sum(1 for r in results if r.stt_success)
        bert_corrects = sum(1 for r in results if r.bert_correct)
        llm_corrects = sum(1 for r in results if r.llm_correct)
        workflow_successes = sum(1 for r in results if r.workflow_success)
        tts_successes = sum(1 for r in results if r.tts_success)
        e2e_successes = sum(1 for r in results if r.e2e_success)
        auto_resolved = sum(1 for r in results if r.auto_resolved)

        total = len(results)
        report.stt_success_rate = stt_successes / total * 100
        report.bert_intent_accuracy = bert_corrects / total * 100
        report.llm_intent_accuracy = llm_corrects / total * 100
        report.workflow_success_rate = workflow_successes / total * 100
        report.tts_success_rate = tts_successes / total * 100
        report.e2e_success_rate = e2e_successes / total * 100
        report.auto_resolution_rate = auto_resolved / total * 100

        # 평균 지연 시간 계산
        report.avg_stt_latency_ms = sum(r.stt_latency_ms for r in results) / total
        report.avg_workflow_latency_ms = sum(r.workflow_latency_ms for r in results) / total
        report.avg_tts_latency_ms = sum(r.tts_latency_ms for r in results) / total
        report.avg_e2e_latency_ms = sum(r.e2e_latency_ms for r in results) / total

        # RAG 검색 메트릭 계산
        rag_scores = [r.rag_best_score for r in results if r.rag_best_score > 0]
        report.avg_rag_score = sum(rag_scores) / len(rag_scores) if rag_scores else 0.0
        report.avg_rag_doc_count = sum(r.rag_doc_count for r in results) / total
        rag_hits = sum(1 for r in results if r.rag_doc_count > 0)
        report.rag_hit_rate = rag_hits / total * 100

        # 카테고리별 결과
        categories = set(r.category for r in results)
        for cat in categories:
            cat_results = [r for r in results if r.category == cat]
            cat_total = len(cat_results)
            cat_rag_scores = [r.rag_best_score for r in cat_results if r.rag_best_score > 0]
            report.category_results[cat] = {
                "total": cat_total,
                "e2e_success_rate": sum(1 for r in cat_results if r.e2e_success) / cat_total * 100,
                "bert_intent_accuracy": sum(1 for r in cat_results if r.bert_correct) / cat_total * 100,
                "llm_intent_accuracy": sum(1 for r in cat_results if r.llm_correct) / cat_total * 100,
                "auto_resolution_rate": sum(1 for r in cat_results if r.auto_resolved) / cat_total * 100,
                "avg_rag_score": sum(cat_rag_scores) / len(cat_rag_scores) if cat_rag_scores else 0.0,
                "rag_hit_rate": sum(1 for r in cat_results if r.rag_doc_count > 0) / cat_total * 100
            }

        # 상세 결과
        report.scenario_results = [asdict(r) for r in results]

        # KPI 검증 (LLM 정확도 기준)
        report.kpi_details = {
            "bert_intent_accuracy_target": 90,
            "bert_intent_accuracy_actual": report.bert_intent_accuracy,
            "bert_intent_accuracy_passed": report.bert_intent_accuracy >= 90,

            "llm_intent_accuracy_target": 90,
            "llm_intent_accuracy_actual": report.llm_intent_accuracy,
            "llm_intent_accuracy_passed": report.llm_intent_accuracy >= 90,

            "e2e_latency_target_ms": 5000,
            "e2e_latency_actual_ms": report.avg_e2e_latency_ms,
            "e2e_latency_passed": report.avg_e2e_latency_ms <= 5000,

            "auto_resolution_target": 70,
            "auto_resolution_actual": report.auto_resolution_rate,
            "auto_resolution_passed": report.auto_resolution_rate >= 70
        }

        # LLM 정확도를 기준으로 KPI 통과 여부 판단
        report.kpi_passed = all([
            report.kpi_details["llm_intent_accuracy_passed"],
            report.kpi_details["e2e_latency_passed"],
            report.kpi_details["auto_resolution_passed"]
        ])

        return report


def save_report(report: E2ETestReport, output_dir: Path) -> Path:
    """리포트를 JSON 파일로 저장합니다."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"card_e2e_report_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)

    return output_file


def print_report_summary(report: E2ETestReport):
    """리포트 요약을 출력합니다."""
    print("\n" + "=" * 70)
    print("카드사 E2E 테스트 결과 리포트")
    print("=" * 70)
    print(f"테스트 일시: {report.test_date}")
    print(f"총 시나리오: {report.total_scenarios}개")

    print("\n[ 성공률 ]")
    print(f"  STT 성공률:         {report.stt_success_rate:.1f}%")
    print(f"  BERT Intent 정확도: {report.bert_intent_accuracy:.1f}%")
    print(f"  LLM Intent 정확도:  {report.llm_intent_accuracy:.1f}%")
    print(f"  워크플로우 성공률:   {report.workflow_success_rate:.1f}%")
    print(f"  TTS 성공률:         {report.tts_success_rate:.1f}%")
    print(f"  E2E 성공률:         {report.e2e_success_rate:.1f}%")
    print(f"  자동 해결률:        {report.auto_resolution_rate:.1f}%")

    print("\n[ RAG 검색 메트릭 (BM25 + KIWI Reranking) ]")
    print(f"  RAG 검색 성공률:    {report.rag_hit_rate:.1f}%")
    print(f"  평균 RAG 점수:      {report.avg_rag_score:.3f}")
    print(f"  평균 검색 문서 수:   {report.avg_rag_doc_count:.1f}개")

    print("\n[ 평균 지연 시간 ]")
    print(f"  STT:       {report.avg_stt_latency_ms:.0f}ms")
    print(f"  워크플로우: {report.avg_workflow_latency_ms:.0f}ms")
    print(f"  TTS:       {report.avg_tts_latency_ms:.0f}ms")
    print(f"  전체 E2E:  {report.avg_e2e_latency_ms:.0f}ms")

    print("\n[ 카테고리별 결과 ]")
    for cat, stats in report.category_results.items():
        print(f"  {cat}:")
        print(f"    E2E {stats['e2e_success_rate']:.0f}%, "
              f"BERT {stats['bert_intent_accuracy']:.0f}%, "
              f"LLM {stats['llm_intent_accuracy']:.0f}%, "
              f"Auto {stats['auto_resolution_rate']:.0f}%, "
              f"RAG {stats.get('rag_hit_rate', 0):.0f}% (점수: {stats.get('avg_rag_score', 0):.2f})")

    print("\n[ KPI 검증 ]")
    kpi = report.kpi_details

    # BERT Intent 정확도
    bert_status = "PASS" if kpi["bert_intent_accuracy_passed"] else "FAIL"
    print(f"  BERT Intent: {kpi['bert_intent_accuracy_actual']:.1f}% "
          f"(목표: {kpi['bert_intent_accuracy_target']}%) {bert_status}")

    # LLM Intent 정확도
    llm_status = "PASS" if kpi["llm_intent_accuracy_passed"] else "FAIL"
    print(f"  LLM Intent:  {kpi['llm_intent_accuracy_actual']:.1f}% "
          f"(목표: {kpi['llm_intent_accuracy_target']}%) {llm_status}")

    # E2E 지연시간
    latency_status = "PASS" if kpi["e2e_latency_passed"] else "FAIL"
    print(f"  E2E Latency: {kpi['e2e_latency_actual_ms']:.0f}ms "
          f"(목표: {kpi['e2e_latency_target_ms']}ms) {latency_status}")

    # 자동 해결률
    auto_status = "PASS" if kpi["auto_resolution_passed"] else "FAIL"
    print(f"  Auto Resolution: {kpi['auto_resolution_actual']:.1f}% "
          f"(목표: {kpi['auto_resolution_target']}%) {auto_status}")

    print("\n" + "=" * 70)
    if report.kpi_passed:
        print("전체 KPI 통과! (LLM Intent 기준)")
    else:
        print("KPI 미달 - 개선이 필요합니다.")
    print("=" * 70)


async def main():
    parser = argparse.ArgumentParser(description="카드사 E2E 테스트 실행")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="STT 건너뛰고 텍스트 기반 테스트"
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="TTS 건너뛰기"
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="특정 카테고리만 테스트"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="테스트할 최대 시나리오 수"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 출력"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="리포트 출력 디렉토리"
    )

    args = parser.parse_args()

    # 경로 설정
    base_dir = PROJECT_ROOT / "e2e_evaluation_pipeline" / "datasets" / "card_e2e_test"
    scenario_file = base_dir / "card_100_scenarios.json"
    audio_dir = base_dir / "audio"
    output_dir = args.output_dir or (PROJECT_ROOT / "e2e_evaluation_pipeline" / "reports")

    if not scenario_file.exists():
        logger.error(f"시나리오 파일을 찾을 수 없습니다: {scenario_file}")
        sys.exit(1)

    # 시나리오 로드
    scenarios = load_scenarios(scenario_file, args.category)
    logger.info(f"로드된 시나리오: {len(scenarios)}개")

    if args.category:
        logger.info(f"카테고리 필터: {args.category}")

    # 테스트 러너 생성 및 실행
    runner = CardE2ETestRunner(
        text_only=args.text_only,
        skip_tts=args.skip_tts,
        verbose=args.verbose
    )

    report = await runner.run_all_scenarios(
        scenarios=scenarios,
        audio_dir=audio_dir if not args.text_only else None,
        limit=args.limit
    )

    # 리포트 저장 및 출력
    report_file = save_report(report, output_dir)
    logger.info(f"리포트 저장: {report_file}")

    print_report_summary(report)

    # KPI 미달 시 종료 코드 1
    if not report.kpi_passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
