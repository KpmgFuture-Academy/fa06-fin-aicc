"""
Evaluation Pipeline Configuration
=================================

평가 파이프라인 설정 관리
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class EvaluationMode(str, Enum):
    """평가 모드"""
    FULL = "full"           # 전체 평가
    QUICK = "quick"         # 빠른 평가 (샘플링)
    MODULE = "module"       # 특정 모듈만
    CI = "ci"               # CI/CD용 (P0만)


@dataclass
class PathConfig:
    """경로 설정"""
    # 프로젝트 루트
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # 평가 파이프라인 루트
    eval_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def datasets_dir(self) -> Path:
        return self.eval_root / "datasets"

    @property
    def reports_dir(self) -> Path:
        return self.eval_root / "reports"

    @property
    def metrics_dir(self) -> Path:
        return self.eval_root / "metrics"

    @property
    def ai_engine_dir(self) -> Path:
        return self.project_root / "ai_engine"

    @property
    def models_dir(self) -> Path:
        return self.project_root / "models"

    @property
    def chroma_db_path(self) -> Path:
        return self.project_root / "chroma_db"

    def ensure_dirs(self):
        """필요한 디렉토리 생성"""
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        (self.datasets_dir / "golden_qa").mkdir(exist_ok=True)
        (self.datasets_dir / "intent_test").mkdir(exist_ok=True)
        (self.datasets_dir / "stt_test").mkdir(exist_ok=True)
        (self.datasets_dir / "tts_test").mkdir(exist_ok=True)
        (self.datasets_dir / "slot_test").mkdir(exist_ok=True)
        (self.datasets_dir / "summary_test").mkdir(exist_ok=True)


@dataclass
class STTEvalConfig:
    """STT 평가 설정"""
    enabled: bool = True
    use_vito: bool = True
    test_audio_dir: str = "datasets/stt_test"
    financial_terms_file: str = "datasets/financial_terms.json"
    sample_size: Optional[int] = None  # None이면 전체


@dataclass
class IntentEvalConfig:
    """Intent 분류 평가 설정"""
    enabled: bool = True
    test_data_file: str = "datasets/intent_test/test_data.json"
    model_path: Optional[str] = None  # None이면 기본 경로
    batch_size: int = 32
    compute_confusion_matrix: bool = True


@dataclass
class RAGEvalConfig:
    """RAG 평가 설정"""
    enabled: bool = True
    golden_qa_file: str = "datasets/golden_qa/qa_set.json"
    top_k: int = 3
    top_k_retrieval: int = 20
    evaluate_bm25_contribution: bool = True
    evaluate_rerank_effectiveness: bool = True
    use_ragas: bool = True  # RAGAS 프레임워크 사용


@dataclass
class SlotFillingEvalConfig:
    """Slot Filling 평가 설정"""
    enabled: bool = True
    test_dialogues_file: str = "datasets/slot_test/dialogues.json"
    required_fields: List[str] = field(default_factory=lambda: [
        "customer_name",
        "inquiry_type",
        "inquiry_detail"
    ])


@dataclass
class SummaryEvalConfig:
    """Summary 평가 설정"""
    enabled: bool = True
    test_data_file: str = "datasets/summary_test/test_data.json"
    compute_rouge: bool = True
    compute_sentiment: bool = True
    reference_summaries_required: bool = True


@dataclass
class FlowEvalConfig:
    """LangGraph Flow 평가 설정"""
    enabled: bool = True
    expected_flows_file: str = "datasets/expected_flows.json"
    measure_latency: bool = True
    detect_infinite_loops: bool = True
    max_node_visits: int = 20  # 무한 루프 감지 임계값


@dataclass
class TTSEvalConfig:
    """TTS 평가 설정"""
    enabled: bool = True
    use_google: bool = True  # False면 OpenAI TTS
    test_data_file: str = "datasets/tts_test/test_data.json"
    default_voice: Optional[str] = None
    sample_size: Optional[int] = None  # None이면 전체


@dataclass
class E2EEvalConfig:
    """E2E 통합 평가 설정"""
    enabled: bool = True
    test_scenarios_file: str = "datasets/e2e_scenarios.json"
    measure_latency: bool = True
    timeout_seconds: int = 30


@dataclass
class ReportConfig:
    """리포트 설정"""
    output_format: str = "html"  # html, json, markdown
    include_charts: bool = True
    include_details: bool = True
    compare_with_benchmark: bool = True
    save_raw_results: bool = True


@dataclass
class EvaluationConfig:
    """전체 평가 설정"""
    mode: EvaluationMode = EvaluationMode.FULL
    paths: PathConfig = field(default_factory=PathConfig)

    # 모듈별 설정
    stt: STTEvalConfig = field(default_factory=STTEvalConfig)
    tts: TTSEvalConfig = field(default_factory=TTSEvalConfig)
    intent: IntentEvalConfig = field(default_factory=IntentEvalConfig)
    rag: RAGEvalConfig = field(default_factory=RAGEvalConfig)
    slot_filling: SlotFillingEvalConfig = field(default_factory=SlotFillingEvalConfig)
    summary: SummaryEvalConfig = field(default_factory=SummaryEvalConfig)
    flow: FlowEvalConfig = field(default_factory=FlowEvalConfig)
    e2e: E2EEvalConfig = field(default_factory=E2EEvalConfig)

    # 리포트 설정
    report: ReportConfig = field(default_factory=ReportConfig)

    # 실행 설정
    parallel: bool = False
    verbose: bool = True
    seed: int = 42

    def __post_init__(self):
        """초기화 후 처리"""
        self.paths.ensure_dirs()

    @classmethod
    def for_ci(cls) -> "EvaluationConfig":
        """CI/CD용 설정 (P0 메트릭만, 빠른 실행)"""
        config = cls(mode=EvaluationMode.CI)
        config.stt.sample_size = 50
        config.report.include_charts = False
        config.verbose = False
        return config

    @classmethod
    def for_quick_test(cls) -> "EvaluationConfig":
        """빠른 테스트용 설정"""
        config = cls(mode=EvaluationMode.QUICK)
        config.stt.sample_size = 20
        config.rag.use_ragas = False
        return config

    @classmethod
    def for_module(cls, module_name: str) -> "EvaluationConfig":
        """특정 모듈만 평가"""
        config = cls(mode=EvaluationMode.MODULE)

        # 모든 모듈 비활성화
        config.stt.enabled = False
        config.tts.enabled = False
        config.intent.enabled = False
        config.rag.enabled = False
        config.slot_filling.enabled = False
        config.summary.enabled = False
        config.flow.enabled = False
        config.e2e.enabled = False

        # 지정 모듈만 활성화
        module_map = {
            "stt": config.stt,
            "tts": config.tts,
            "intent": config.intent,
            "rag": config.rag,
            "slot_filling": config.slot_filling,
            "summary": config.summary,
            "flow": config.flow,
            "e2e": config.e2e
        }

        if module_name in module_map:
            module_map[module_name].enabled = True
        else:
            raise ValueError(f"Unknown module: {module_name}. Available: {list(module_map.keys())}")

        return config


# 환경변수에서 설정 로드
def load_config_from_env() -> EvaluationConfig:
    """환경변수에서 설정 로드"""
    config = EvaluationConfig()

    # 모드 설정
    mode = os.getenv("EVAL_MODE", "full").lower()
    if mode in [m.value for m in EvaluationMode]:
        config.mode = EvaluationMode(mode)

    # 병렬 실행
    config.parallel = os.getenv("EVAL_PARALLEL", "false").lower() == "true"

    # 상세 로그
    config.verbose = os.getenv("EVAL_VERBOSE", "true").lower() == "true"

    return config


# 기본 설정 인스턴스
DEFAULT_CONFIG = EvaluationConfig()
