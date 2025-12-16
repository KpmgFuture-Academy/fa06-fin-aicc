# E2E Evaluation Pipeline

KPMG 6기 2팀 카드사 AICC 자동화 시스템의 E2E 평가 파이프라인

## 개요

이 파이프라인은 AICC 시스템의 각 모듈과 전체 E2E 성능을 평가합니다.

### 평가 대상 모듈

| 모듈 | 설명 | 주요 메트릭 |
|------|------|-------------|
| STT | VITO STT 음성인식 | CER, WER, Segmentation Count |
| Intent | KcELECTRA 의도분류 | Accuracy, F1, HUMAN_REQUIRED Recall |
| RAG | Hybrid Search (Vector+BM25+Rerank) | Precision@K, MRR, BM25 Contribution |
| Slot Filling | Waiting Agent 정보수집 | Completion Rate, Field Accuracy |
| Summary | 대화 요약 | ROUGE-L, Omission Rate |
| Flow | LangGraph 워크플로우 | Transition Accuracy, Node Latency |
| E2E | 전체 시스템 | Auto Resolution Rate, E2E Latency, CSAT |

## 설치

```bash
pip install -r requirements.txt
```

## 사용법

### 전체 평가 실행

```bash
# 빠른 평가 (샘플링)
python -m e2e_evaluation_pipeline --mode quick

# 전체 평가
python -m e2e_evaluation_pipeline --mode full

# CI/CD 모드 (P0 메트릭만)
python -m e2e_evaluation_pipeline --mode ci
```

### 특정 모듈 평가

```bash
python -m e2e_evaluation_pipeline --module stt
python -m e2e_evaluation_pipeline --module intent
python -m e2e_evaluation_pipeline --module rag
python -m e2e_evaluation_pipeline --module slot_filling
python -m e2e_evaluation_pipeline --module summary
python -m e2e_evaluation_pipeline --module flow
```

### Python API 사용

```python
from e2e_evaluation_pipeline.runners.e2e_runner import E2EEvaluationRunner
from e2e_evaluation_pipeline.configs.config import EvaluationConfig, EvaluationMode

# 설정 생성
config = EvaluationConfig(mode=EvaluationMode.FULL)

# 평가 실행
runner = E2EEvaluationRunner(config)
result = runner.run(test_data)

# 결과 확인
print(f"Overall Passed: {result.overall_passed}")
print(f"P0 Passed: {result.p0_passed}")
```

## KPI 우선순위

| 우선순위 | 설명 | 예시 |
|----------|------|------|
| P0 | Critical - 반드시 통과해야 함 | HUMAN_REQUIRED Recall, Auto Resolution Rate |
| P1 | High - 중요 품질 지표 | CER, Accuracy, ROUGE-L |
| P2 | Medium - 참고 지표 | Top-3 Accuracy, BM25 Contribution |

## 산업 벤치마크

| 메트릭 | 목표 | 산업 벤치마크 | 출처 |
|--------|------|---------------|------|
| CER | ≤5% | 5-7% | Plivo, Retell AI |
| E2E Latency | ≤3s | ≤800ms | Plivo |
| FCR | ≥75% | 70-80% | Contact Center Industry |
| CSAT | ≥80% | 75-85% | Contact Center Industry |
| Auto Resolution | ≥70% | 60-80% | Gartner |

## 리포트 형식

- **HTML**: 시각적 대시보드 형식
- **JSON**: 프로그래밍 처리용
- **Markdown**: 문서화용

```bash
python -m e2e_evaluation_pipeline --mode full --report html json md
```

## 디렉토리 구조

```
e2e_evaluation_pipeline/
├── __init__.py
├── __main__.py
├── README.md
├── configs/
│   ├── __init__.py
│   ├── config.py
│   └── kpi_thresholds.py
├── metrics/
│   ├── __init__.py
│   ├── base.py
│   ├── stt_metrics.py
│   ├── intent_metrics.py
│   ├── rag_metrics.py
│   ├── slot_metrics.py
│   ├── summary_metrics.py
│   ├── flow_metrics.py
│   └── e2e_metrics.py
├── runners/
│   ├── __init__.py
│   ├── e2e_runner.py
│   └── module_runner.py
├── reports/
│   ├── __init__.py
│   └── report_generator.py
└── datasets/
    ├── __init__.py
    ├── data_loader.py
    ├── stt_test/
    ├── intent_test/
    ├── golden_qa/
    ├── slot_test/
    ├── summary_test/
    ├── flow_test/
    └── e2e_test/
```

## CI/CD 통합

GitHub Actions 예시:

```yaml
- name: Run E2E Evaluation
  run: |
    python -m e2e_evaluation_pipeline --mode ci
```

P0 메트릭 실패 시 exit code 1 반환.
