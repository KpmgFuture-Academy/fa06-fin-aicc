"""
KPI Thresholds and Industry Benchmark Standards
================================================

프로젝트 KPI 목표와 업계 벤치마크 기준 정의

Reference Sources:
    - STT: https://blog.rtzr.ai/korean-speechai-benchmark/
    - Contact Center: https://www.plivo.com/blog/contact-center-statistics-benchmarks-2025/
    - RAG: https://www.tweag.io/blog/2025-02-27-rag-evaluation/
    - Voice Latency: https://www.retellai.com/resources/ai-voice-agent-latency-face-off-2025
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional


class Priority(str, Enum):
    """KPI 우선순위"""
    P0 = "P0"  # 필수 (Critical)
    P1 = "P1"  # 중요 (Important)
    P2 = "P2"  # 참고 (Nice to have)


class EvaluationLevel(str, Enum):
    """평가 결과 수준"""
    WORLD_CLASS = "world_class"  # 상위 5%
    EXCELLENT = "excellent"       # 우수
    GOOD = "good"                # 양호
    NEEDS_IMPROVEMENT = "needs_improvement"  # 개선 필요
    CRITICAL = "critical"        # 심각


@dataclass
class KPIMetric:
    """개별 KPI 메트릭 정의"""
    name: str
    target: float
    unit: str
    priority: Priority
    higher_is_better: bool = True
    description: str = ""

    # 업계 벤치마크 기준
    industry_average: Optional[float] = None
    world_class: Optional[float] = None

    def evaluate(self, actual: float) -> EvaluationLevel:
        """실제 값을 기준과 비교하여 수준 평가"""
        if self.higher_is_better:
            if self.world_class and actual >= self.world_class:
                return EvaluationLevel.WORLD_CLASS
            elif actual >= self.target:
                return EvaluationLevel.EXCELLENT
            elif self.industry_average and actual >= self.industry_average:
                return EvaluationLevel.GOOD
            elif actual >= self.target * 0.8:
                return EvaluationLevel.NEEDS_IMPROVEMENT
            else:
                return EvaluationLevel.CRITICAL
        else:
            # Lower is better (예: Error Rate, Latency)
            if self.world_class and actual <= self.world_class:
                return EvaluationLevel.WORLD_CLASS
            elif actual <= self.target:
                return EvaluationLevel.EXCELLENT
            elif self.industry_average and actual <= self.industry_average:
                return EvaluationLevel.GOOD
            elif actual <= self.target * 1.2:
                return EvaluationLevel.NEEDS_IMPROVEMENT
            else:
                return EvaluationLevel.CRITICAL


@dataclass
class KPIThresholds:
    """프로젝트 KPI 목표값 정의"""

    # ========================================
    # A. STT (Speech-to-Text) 성능평가
    # ========================================
    stt: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "cer": KPIMetric(
            name="CER (Character Error Rate)",
            target=10.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="한국어 음성 인식 문자 오류율",
            industry_average=11.0,
            world_class=8.0
        ),
        "wer": KPIMetric(
            name="WER (Word Error Rate)",
            target=15.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=False,
            description="단어 오류율 (참고용)",
            industry_average=15.0,
            world_class=10.0
        ),
        "segmentation_count": KPIMetric(
            name="Segmentation Count",
            target=8.0,
            unit="개",
            priority=Priority.P0,
            higher_is_better=False,
            description="평균 분절 수 (요약 품질 직결)",
            industry_average=10.0,
            world_class=7.0
        ),
        "wrong_segmentation_rate": KPIMetric(
            name="Wrong Segmentation Rate",
            target=10.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=False,
            description="미세침묵으로 인한 불필요한 분절 비율"
        ),
        "financial_term_accuracy": KPIMetric(
            name="Financial Term Accuracy",
            target=95.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="금융 전문용어 인식률",
            industry_average=90.0,
            world_class=98.0
        ),
        "speaker_diarization_accuracy": KPIMetric(
            name="Speaker Diarization Accuracy",
            target=90.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=True,
            description="화자 분리 정확도"
        ),
        "latency_ttfb": KPIMetric(
            name="Latency (TTFB)",
            target=300.0,
            unit="ms",
            priority=Priority.P1,
            higher_is_better=False,
            description="첫 응답까지 시간",
            industry_average=300.0,
            world_class=200.0
        ),
    })

    # ========================================
    # B. Intent Classification 성능평가
    # ========================================
    intent: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "accuracy": KPIMetric(
            name="Intent Accuracy",
            target=75.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="의도 분류 정확도",
            industry_average=85.0,
            world_class=95.0
        ),
        "weighted_f1": KPIMetric(
            name="Weighted F1 Score",
            target=75.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="가중 F1 점수 (클래스 불균형 반영)"
        ),
        "macro_f1": KPIMetric(
            name="Macro F1 Score",
            target=65.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="매크로 F1 점수"
        ),
        "human_required_recall": KPIMetric(
            name="HUMAN_REQUIRED Recall",
            target=90.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="상담사 연결 필요 케이스 탐지율 (미탐 방지)"
        ),
        "top3_accuracy": KPIMetric(
            name="Top-3 Accuracy",
            target=90.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=True,
            description="상위 3개 예측 중 정답 포함률"
        ),
    })

    # ========================================
    # C. Triage (판단 에이전트) 성능평가
    # ========================================
    triage: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "overall_accuracy": KPIMetric(
            name="Triage Overall Accuracy",
            target=85.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="4개 클래스 전체 분류 정확도"
        ),
        "simple_answer_precision": KPIMetric(
            name="SIMPLE_ANSWER Precision",
            target=90.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="단순 반응/인사 판별 정밀도"
        ),
        "auto_answer_match_rate": KPIMetric(
            name="AUTO_ANSWER Match Rate",
            target=90.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="RAG 답변 가능 여부 실제 일치율"
        ),
        "need_more_info_accuracy": KPIMetric(
            name="NEED_MORE_INFO Accuracy",
            target=85.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="추가 정보 필요 판단 정확도"
        ),
        "human_required_fn_rate": KPIMetric(
            name="HUMAN_REQUIRED FN Rate",
            target=5.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="상담사 연결 미탐율 (False Negative)"
        ),
    })

    # ========================================
    # D. RAG Hybrid Search 성능평가
    # ========================================
    rag: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "precision_at_3": KPIMetric(
            name="Precision@3",
            target=85.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="Top 3 문서 중 정답 포함 비율",
            industry_average=60.0,
            world_class=90.0
        ),
        "recall_at_20": KPIMetric(
            name="Recall@20",
            target=95.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="벡터 검색 단계 정답 포함률"
        ),
        "mrr": KPIMetric(
            name="MRR (Mean Reciprocal Rank)",
            target=0.7,
            unit="score",
            priority=Priority.P1,
            higher_is_better=True,
            description="정답 문서 순위 역수 평균",
            industry_average=0.6,
            world_class=0.8
        ),
        "ndcg_at_3": KPIMetric(
            name="NDCG@3",
            target=0.85,
            unit="score",
            priority=Priority.P1,
            higher_is_better=True,
            description="순위 가중 정규화 점수"
        ),
        "bm25_contribution": KPIMetric(
            name="BM25 Contribution",
            target=15.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="BM25로 순위 상승한 정답 비율"
        ),
        "rerank_effectiveness": KPIMetric(
            name="Rerank Effectiveness",
            target=20.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="Reranking으로 순위 개선된 비율"
        ),
        "financial_keyword_match": KPIMetric(
            name="Financial Keyword Match",
            target=95.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=True,
            description="금융 도메인 키워드 매칭률"
        ),
        "low_confidence_rate": KPIMetric(
            name="Low Confidence Rate",
            target=10.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=False,
            description="score < 0.5인 결과 비율"
        ),
        "faithfulness": KPIMetric(
            name="Faithfulness",
            target=0.85,
            unit="score",
            priority=Priority.P0,
            higher_is_better=True,
            description="생성 답변의 컨텍스트 충실도",
            industry_average=0.80,
            world_class=0.90
        ),
        "answer_relevancy": KPIMetric(
            name="Answer Relevancy",
            target=0.85,
            unit="score",
            priority=Priority.P0,
            higher_is_better=True,
            description="답변의 질문 관련성"
        ),
    })

    # ========================================
    # E. Slot Filling 성능평가
    # ========================================
    slot_filling: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "completion_rate": KPIMetric(
            name="Slot Completion Rate",
            target=90.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="모든 필수 필드 수집 완료율",
            industry_average=85.0,
            world_class=95.0
        ),
        "customer_name_accuracy": KPIMetric(
            name="Customer Name Extraction Accuracy",
            target=90.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="고객명 추출 정확도"
        ),
        "inquiry_type_accuracy": KPIMetric(
            name="Inquiry Type Extraction Accuracy",
            target=90.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="문의 유형 추출 정확도"
        ),
        "inquiry_detail_accuracy": KPIMetric(
            name="Inquiry Detail Extraction Accuracy",
            target=90.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="상세 내용 추출 정확도"
        ),
        "avg_turns": KPIMetric(
            name="Average Slot Filling Turns",
            target=3.0,
            unit="턴",
            priority=Priority.P1,
            higher_is_better=False,
            description="정보 수집 완료까지 평균 턴 수"
        ),
        "wrong_assignment_rate": KPIMetric(
            name="Wrong Field Assignment Rate",
            target=5.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=False,
            description="잘못된 필드 할당 비율"
        ),
        "failure_to_transfer_rate": KPIMetric(
            name="Slot Failure to Transfer Rate",
            target=10.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="수집 실패로 상담사 연결된 비율"
        ),
        "duplicate_question_rate": KPIMetric(
            name="Duplicate Question Rate",
            target=5.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=False,
            description="이미 답변한 정보를 다시 묻는 비율"
        ),
    })

    # ========================================
    # F. Summary 성능평가
    # ========================================
    summary: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "rouge_l": KPIMetric(
            name="ROUGE-L Score",
            target=0.65,
            unit="score",
            priority=Priority.P0,
            higher_is_better=True,
            description="참조 요약 대비 일치도 (LCS 기반)",
            industry_average=0.50,
            world_class=0.70
        ),
        "rouge_1": KPIMetric(
            name="ROUGE-1 Score",
            target=0.60,
            unit="score",
            priority=Priority.P1,
            higher_is_better=True,
            description="단어 단위 일치도"
        ),
        "rouge_2": KPIMetric(
            name="ROUGE-2 Score",
            target=0.40,
            unit="score",
            priority=Priority.P1,
            higher_is_better=True,
            description="바이그램 일치도"
        ),
        "info_omission_rate": KPIMetric(
            name="Information Omission Rate",
            target=10.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="핵심 정보 누락 비율"
        ),
        "hallucination_rate": KPIMetric(
            name="Hallucination Rate",
            target=5.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="없는 정보가 추가된 비율"
        ),
        "sentiment_accuracy": KPIMetric(
            name="Sentiment Classification Accuracy",
            target=80.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="감정 분류 정확도 (POSITIVE/NEGATIVE/NEUTRAL)"
        ),
        "keyword_accuracy": KPIMetric(
            name="Keyword Extraction Accuracy",
            target=80.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=True,
            description="핵심 키워드 5개 적절성"
        ),
        "agent_satisfaction": KPIMetric(
            name="Agent Satisfaction Score",
            target=4.0,
            unit="점 (1-5)",
            priority=Priority.P1,
            higher_is_better=True,
            description="요약 품질에 대한 상담원 평가"
        ),
        "repeat_explanation_rate": KPIMetric(
            name="Repeat Explanation Request Rate",
            target=10.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="상담원이 고객에게 다시 묻는 비율"
        ),
    })

    # ========================================
    # G. LangGraph Flow 성능평가
    # ========================================
    flow: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "transition_accuracy": KPIMetric(
            name="Node Transition Accuracy",
            target=95.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="예상 경로와 실제 경로 일치율"
        ),
        "fallback_rate": KPIMetric(
            name="Fallback Rate",
            target=5.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="예외 처리로 빠지는 비율"
        ),
        "infinite_loop_rate": KPIMetric(
            name="Infinite Loop Rate",
            target=0.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=False,
            description="동일 노드 반복 진입 비율"
        ),
        "session_completion_rate": KPIMetric(
            name="Session Completion Rate",
            target=95.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="정상 종료된 세션 비율"
        ),
        "avg_node_visits": KPIMetric(
            name="Average Node Visits",
            target=8.0,
            unit="개",
            priority=Priority.P2,
            higher_is_better=False,
            description="세션당 평균 노드 방문 횟수"
        ),
        # 노드별 Latency
        "latency_triage_agent": KPIMetric(
            name="Triage Agent Latency",
            target=1500.0,
            unit="ms",
            priority=Priority.P1,
            higher_is_better=False,
            description="판단 에이전트 처리 시간"
        ),
        "latency_answer_agent": KPIMetric(
            name="Answer Agent Latency",
            target=2000.0,
            unit="ms",
            priority=Priority.P1,
            higher_is_better=False,
            description="답변 에이전트 처리 시간"
        ),
        "latency_waiting_agent": KPIMetric(
            name="Waiting Agent Latency",
            target=1500.0,
            unit="ms",
            priority=Priority.P1,
            higher_is_better=False,
            description="대기시간 에이전트 처리 시간"
        ),
        "latency_summary_agent": KPIMetric(
            name="Summary Agent Latency",
            target=2000.0,
            unit="ms",
            priority=Priority.P1,
            higher_is_better=False,
            description="요약 에이전트 처리 시간"
        ),
        "latency_db_storage": KPIMetric(
            name="DB Storage Latency",
            target=500.0,
            unit="ms",
            priority=Priority.P1,
            higher_is_better=False,
            description="DB 저장 처리 시간"
        ),
    })

    # ========================================
    # H. TTS (Text-to-Speech) 성능평가
    # ========================================
    tts: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "synthesis_latency": KPIMetric(
            name="Synthesis Latency",
            target=500.0,
            unit="ms",
            priority=Priority.P0,
            higher_is_better=False,
            description="음성 합성 시간",
            industry_average=600.0,
            world_class=300.0
        ),
        "success_rate": KPIMetric(
            name="Success Rate",
            target=99.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="음성 합성 성공률"
        ),
        "chars_per_second": KPIMetric(
            name="Characters Per Second",
            target=50.0,
            unit="chars/s",
            priority=Priority.P1,
            higher_is_better=True,
            description="초당 처리 문자 수"
        ),
        "audio_quality_ratio": KPIMetric(
            name="Audio Quality Ratio",
            target=100.0,
            unit="bytes/char",
            priority=Priority.P2,
            higher_is_better=True,
            description="문자당 오디오 크기 (품질 지표)"
        ),
    })

    # ========================================
    # I. E2E (전체 시스템) 성능평가
    # ========================================
    e2e: Dict[str, KPIMetric] = field(default_factory=lambda: {
        "auto_resolution_rate": KPIMetric(
            name="Auto Resolution Rate",
            target=40.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="AI가 자동 해결한 비율",
            industry_average=35.0,
            world_class=70.0
        ),
        "e2e_latency": KPIMetric(
            name="E2E Response Latency",
            target=3000.0,
            unit="ms",
            priority=Priority.P0,
            higher_is_better=False,
            description="음성입력→음성응답 전체 시간",
            industry_average=1500.0,
            world_class=800.0
        ),
        "repeat_explanation_reduction": KPIMetric(
            name="Repeat Explanation Reduction",
            target=70.0,
            unit="%",
            priority=Priority.P0,
            higher_is_better=True,
            description="고객 반복 설명 감소율 (대화 블랙홀 해소)"
        ),
        "aht_reduction": KPIMetric(
            name="AHT Reduction",
            target=20.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="상담사 평균 처리 시간 감소율"
        ),
        "transfer_failure_rate": KPIMetric(
            name="Transfer Failure Rate",
            target=5.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=False,
            description="상담사 연결 실패율"
        ),
        "csat": KPIMetric(
            name="CSAT (Customer Satisfaction)",
            target=80.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="고객 만족도",
            industry_average=75.0,
            world_class=85.0
        ),
        "fcr": KPIMetric(
            name="FCR (First Contact Resolution)",
            target=70.0,
            unit="%",
            priority=Priority.P1,
            higher_is_better=True,
            description="첫 응대 해결률",
            industry_average=71.0,
            world_class=80.0
        ),
        "system_availability": KPIMetric(
            name="System Availability",
            target=99.0,
            unit="%",
            priority=Priority.P2,
            higher_is_better=True,
            description="시스템 가용성 (Uptime)"
        ),
    })


@dataclass
class BenchmarkStandards:
    """
    업계 벤치마크 기준

    프로젝트 결과와 비교할 수 있는 상업화된 기준값
    """

    # STT 벤치마크 (한국어)
    stt_korean = {
        "provider_rankings": {
            "1st": {"name": "리턴제로 (VITO)", "cer": 8.0},
            "2nd": {"name": "리턴제로 Whisper Fine-tuned", "cer": 8.5},
            "3rd": {"name": "Naver Clova", "cer": 11.0},
            "4th": {"name": "Whisper Large v3", "cer": 11.13},
            "5th": {"name": "Google STT", "cer": 12.0},
        },
        "source": "https://blog.rtzr.ai/korean-speechai-benchmark/",
        "test_dataset": "AI-Hub 테스트셋 (3000문장 샘플링)"
    }

    # Contact Center 벤치마크
    contact_center = {
        "fcr": {
            "needs_improvement": 60,
            "acceptable": 70,
            "good": 75,
            "excellent": 79,
            "world_class": 80,
            "financial_industry_avg": 71
        },
        "csat": {
            "needs_improvement": 65,
            "acceptable": 75,
            "good": 80,
            "excellent": 84,
            "world_class": 85
        },
        "aht_minutes": {
            "world_class": 5,
            "excellent": 6,
            "good": 7,
            "acceptable": 10,
            "financial_industry_avg": 6
        },
        "auto_resolution": {
            "basic": 30,
            "good": 50,
            "excellent": 60,
            "world_class": 70,  # Vodafone TOBi
        },
        "source": "https://www.plivo.com/blog/contact-center-statistics-benchmarks-2025/"
    }

    # Voice Agent Latency 벤치마크
    voice_latency = {
        "natural_conversation": 200,      # 이상적 (ms)
        "acceptable": 500,                 # 수용 가능
        "noticeable_delay": 800,          # 불편함 시작
        "conversation_break": 1000,        # 대화 단절감
        "abandonment_increase": 1000,      # 이탈률 40% 증가 임계점
        "source": "https://www.retellai.com/resources/ai-voice-agent-latency-face-off-2025"
    }

    # RAG 벤치마크
    rag = {
        "context_precision": {
            "gate_threshold": 0.6,  # k=5 기준 최소
            "good": 0.8,
            "excellent": 0.9
        },
        "context_recall": {
            "gate_threshold": 0.8,
            "good": 0.9,
            "excellent": 1.0
        },
        "faithfulness": {
            "acceptable": 0.75,
            "good": 0.85,
            "excellent": 0.90
        },
        "example_scores": {
            "context_recall": 1.0,
            "context_precision": 0.9,
            "faithfulness": 0.85,
            "factual_correctness": 0.87
        },
        "source": "https://www.tweag.io/blog/2025-02-27-rag-evaluation/"
    }

    # Intent Classification 벤치마크
    intent_classification = {
        "general_chatbot": {
            "acceptable": 80,
            "good": 90,
            "excellent": 95,
            "with_5000_examples_per_intent": 98
        },
        "financial_domain": {
            "banking77_sota": 90,
            "production_minimum": 85
        },
        "source": "https://www.artefact.com/blog/nlu-benchmark-for-intent-detection-and-named-entity-recognition-in-call-center-conversations/"
    }

    # Slot Filling 벤치마크
    slot_filling = {
        "f1_score": {
            "acceptable": 80,
            "good": 85,
            "excellent": 90,
            "sota": 95
        },
        "joint_accuracy": {
            "acceptable": 75,
            "good": 80,
            "excellent": 90
        },
        "source": "https://paperswithcode.com/task/slot-filling/codeless"
    }

    # ROUGE Score 벤치마크
    rouge = {
        "general_llm": {
            "rouge_l": 0.25,
            "rouge_1": 0.30
        },
        "fine_tuned": {
            "rouge_l": 0.45,
            "rouge_1": 0.50
        },
        "sota_summarization": {
            "rouge_l": 0.65,
            "rouge_1": 0.70
        },
        "source": "https://www.traceloop.com/blog/evaluating-model-performance-with-the-rouge-metric-a-comprehensive-guide"
    }


# 전역 인스턴스 생성
DEFAULT_KPI_THRESHOLDS = KPIThresholds()
BENCHMARK_STANDARDS = BenchmarkStandards()


def get_all_p0_metrics() -> Dict[str, Dict[str, KPIMetric]]:
    """모든 P0 (필수) 메트릭 반환"""
    kpi = DEFAULT_KPI_THRESHOLDS
    result = {}

    for layer_name in ['stt', 'tts', 'intent', 'triage', 'rag', 'slot_filling', 'summary', 'flow', 'e2e']:
        layer_metrics = getattr(kpi, layer_name)
        p0_metrics = {k: v for k, v in layer_metrics.items() if v.priority == Priority.P0}
        if p0_metrics:
            result[layer_name] = p0_metrics

    return result


def get_metrics_by_priority(priority: Priority) -> Dict[str, Dict[str, KPIMetric]]:
    """특정 우선순위의 메트릭만 반환"""
    kpi = DEFAULT_KPI_THRESHOLDS
    result = {}

    for layer_name in ['stt', 'tts', 'intent', 'triage', 'rag', 'slot_filling', 'summary', 'flow', 'e2e']:
        layer_metrics = getattr(kpi, layer_name)
        filtered = {k: v for k, v in layer_metrics.items() if v.priority == priority}
        if filtered:
            result[layer_name] = filtered

    return result
