# 평가 자동화 가이드

STT, TTS, 의도분류 모델, RAG 검색 평가를 자동화하는 방법에 대한 가이드입니다.

## 개요

프로젝트에는 이미 **E2E 평가 파이프라인**이 구축되어 있습니다. 이 파이프라인을 사용하여 각 모듈의 성능을 자동으로 평가할 수 있습니다.

## 평가 대상 모듈

| 모듈 | 설명 | 주요 메트릭 |
|------|------|-------------|
| **STT** | VITO STT 음성인식 | CER, WER, Segmentation Count |
| **TTS** | Google TTS 음성합성 | Synthesis Time, Success Rate, Error Rate |
| **Intent** | KcELECTRA 의도분류 | Accuracy, F1, HUMAN_REQUIRED Recall |
| **RAG** | Hybrid Search (Vector+BM25+Rerank) | Precision@K, MRR, BM25 Contribution |
| **Slot Filling** | Waiting Agent 정보수집 | Completion Rate, Field Accuracy |
| **Summary** | 대화 요약 | ROUGE-L, Omission Rate |
| **Flow** | LangGraph 워크플로우 | Transition Accuracy, Node Latency |
| **E2E** | 전체 시스템 | Auto Resolution Rate, E2E Latency, CSAT |

## 빠른 시작

### 1. 전체 평가 실행

```bash
# 빠른 평가 (샘플링)
python -m e2e_evaluation_pipeline --mode quick

# 전체 평가
python -m e2e_evaluation_pipeline --mode full

# CI/CD 모드 (P0 메트릭만)
python -m e2e_evaluation_pipeline --mode ci
```

### 2. 특정 모듈만 평가

```bash
# STT 평가
python -m e2e_evaluation_pipeline --module stt

# TTS 평가
python -m e2e_evaluation_pipeline --module tts

# 의도분류 모델 평가
python -m e2e_evaluation_pipeline --module intent

# RAG 검색 평가
python -m e2e_evaluation_pipeline --module rag
```

### 3. 리포트 생성

```bash
# HTML, JSON, Markdown 리포트 생성
python -m e2e_evaluation_pipeline --mode full --report html json md
```

## 각 모듈별 평가 방법

### STT (Speech-to-Text) 평가

**평가 지표:**
- **CER (Character Error Rate)**: 문자 오류율 (목표: ≤10%)
- **WER (Word Error Rate)**: 단어 오류율 (목표: ≤15%)
- **Segmentation Count**: 분절 수 (목표: ≤8개)
- **Financial Term Accuracy**: 금융 전문용어 인식률 (목표: ≥95%)
- **Latency (TTFB)**: 첫 응답까지 시간 (목표: ≤300ms)

**사용 방법:**

```python
from e2e_evaluation_pipeline.adapters.stt_adapter import STTAdapter
from e2e_evaluation_pipeline.metrics.stt_metrics import STTMetrics

# STT 어댑터 초기화
stt_adapter = STTAdapter()

# 음성 파일 인식
result = stt_adapter.transcribe_file("test_audio.wav")

# 평가 실행
test_data = [
    (test_case, stt_result)  # (테스트케이스, STT결과) 튜플 리스트
]
metrics = STTMetrics()
evaluation_result = metrics.evaluate(test_data)
```

**테스트 데이터 준비:**

`e2e_evaluation_pipeline/datasets/stt_test/test_data.json` 형식:
```json
[
  {
    "audio_file": "test1.wav",
    "text": "카드 한도 상향 신청하고 싶어요",
    "expected_segments": 1,
    "financial_terms": ["카드", "한도", "상향"]
  }
]
```

### TTS (Text-to-Speech) 평가

**평가 지표:**
- **Average Synthesis Time**: 평균 합성 시간 (목표: ≤500ms)
- **Success Rate**: 성공률 (목표: ≥99%)
- **Characters per Second**: 초당 문자 처리 속도 (목표: ≥5 chars/s)
- **Error Rate**: 오류율 (목표: ≤1%)

**사용 방법:**

```python
from e2e_evaluation_pipeline.adapters.tts_adapter import TTSAdapter
from e2e_evaluation_pipeline.metrics.tts_metrics import evaluate_tts_from_adapter

# TTS 어댑터 초기화
tts_adapter = TTSAdapter(use_google=True)  # Google TTS 사용

# 평가 실행
texts = [
    "카드 한도 상향 신청하고 싶어요",
    "결제일 변경 문의드립니다",
    "상담원 연결 부탁드립니다"
]

result = evaluate_tts_from_adapter(
    texts=texts,
    tts_adapter=tts_adapter,
    voice="ko-KR-Neural2-B",
    format="mp3"
)

print(f"Success Rate: {result.summary['success_rate']:.2f}%")
print(f"Average Synthesis Time: {result.summary['avg_synthesis_time_ms']:.2f}ms")
```

**명령줄 실행:**

```bash
python -m e2e_evaluation_pipeline --module tts
```

### 의도분류 모델 평가

**평가 지표:**
- **Accuracy**: 전체 정확도 (목표: ≥75%)
- **Weighted F1**: 가중 F1 점수 (목표: ≥75%)
- **Macro F1**: 매크로 F1 점수 (목표: ≥65%)
- **HUMAN_REQUIRED Recall**: 상담사 연결 필요 케이스 탐지율 (목표: ≥90%)
- **Top-3 Accuracy**: 상위 3개 예측 중 정답 포함률 (목표: ≥90%)

**사용 방법:**

```python
from e2e_evaluation_pipeline.metrics.intent_metrics import evaluate_intent_from_model

# 모델 기반 평가
result = evaluate_intent_from_model(
    test_data_path="e2e_evaluation_pipeline/datasets/intent_test/test_data.json",
    model_path=None  # None이면 기본 경로 사용
)

print(f"Accuracy: {result.summary['accuracy']:.2f}%")
print(f"HUMAN_REQUIRED Recall: {result.summary.get('human_required_recall', 0):.2f}%")
```

**테스트 데이터 형식:**

`e2e_evaluation_pipeline/datasets/intent_test/test_data.json`:
```json
[
  {
    "text": "카드 한도 상향 신청하고 싶어요",
    "label": "카드 한도 안내/변경",
    "domain": "카드"
  },
  {
    "text": "상담원 연결 부탁드립니다",
    "label": "상담사 연결",
    "domain": "기타"
  }
]
```

### RAG 검색 평가

**평가 지표:**
- **Precision@3**: Top 3 문서 중 정답 포함 비율 (목표: ≥85%)
- **Recall@20**: 벡터 검색 단계 정답 포함률 (목표: ≥95%)
- **MRR (Mean Reciprocal Rank)**: 정답 문서 순위 역수 평균 (목표: ≥0.7)
- **NDCG@3**: 순위 가중 정규화 점수 (목표: ≥0.85)
- **BM25 Contribution**: BM25 보정 기여도 (목표: ≥15%)
- **Rerank Effectiveness**: Reranking 효과성 (목표: ≥20%)

**사용 방법:**

```python
from ai_engine.vector_store import search_documents
from e2e_evaluation_pipeline.metrics.rag_metrics import evaluate_rag_from_golden_set

# Golden QA 셋 기반 평가
result = evaluate_rag_from_golden_set(
    golden_qa_path="e2e_evaluation_pipeline/datasets/golden_qa/qa_set.json",
    vector_store=vector_store,  # vector_store 인스턴스
    top_k=3
)

print(f"Precision@3: {result.summary['avg_precision_at_3']:.2f}%")
print(f"MRR: {result.summary['avg_mrr']:.4f}")
```

**Golden QA 데이터 형식:**

`e2e_evaluation_pipeline/datasets/golden_qa/qa_set.json`:
```json
[
  {
    "query": "카드 한도 상향 신청 방법",
    "relevant_doc_ids": ["doc1", "doc2"],
    "reference_answer": "카드 한도 상향은...",
    "domain": "카드"
  }
]
```

## Python API 사용

### 개별 모듈 평가

```python
from e2e_evaluation_pipeline.runners.module_runner import (
    run_stt_evaluation,
    run_intent_evaluation,
    run_rag_evaluation
)

# STT 평가
stt_result = run_stt_evaluation(test_data)

# Intent 평가
intent_result = run_intent_evaluation(test_data)

# RAG 평가
rag_result = run_rag_evaluation(test_data)
```

### 전체 E2E 평가

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

## 평가 스크립트 작성 예시

### 예시 1: STT 평가 스크립트

```python
# scripts/evaluate_stt.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from e2e_evaluation_pipeline.adapters.stt_adapter import STTAdapter
from e2e_evaluation_pipeline.metrics.stt_metrics import STTMetrics, STTTestCase, STTResult
import json
import time

def evaluate_stt():
    # STT 어댑터 초기화
    stt_adapter = STTAdapter()
    
    # 테스트 데이터 로드
    with open("e2e_evaluation_pipeline/datasets/stt_test/test_data.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    # 평가 데이터 준비
    eval_data = []
    for item in test_data:
        test_case = STTTestCase(
            audio_path=item["audio_file"],
            reference_text=item["text"],
            expected_segments=item.get("expected_segments"),
            financial_terms=item.get("financial_terms", [])
        )
        
        # STT 실행
        start_time = time.time()
        stt_result = stt_adapter.transcribe_file(test_case.audio_path)
        latency = (time.time() - start_time) * 1000
        
        result = STTResult(
            transcribed_text=stt_result.text,
            segments=[{"text": s.text, "speaker": s.speaker} for s in stt_result.segments],
            latency_ms=latency
        )
        
        eval_data.append((test_case, result))
    
    # 평가 실행
    metrics = STTMetrics()
    result = metrics.evaluate(eval_data)
    
    # 결과 출력
    print(f"\nSTT Evaluation Results:")
    print(f"  CER: {result.summary.get('avg_cer', 0):.2f}%")
    print(f"  WER: {result.summary.get('avg_wer', 0):.2f}%")
    print(f"  Latency: {result.summary.get('avg_latency_ms', 0):.2f}ms")
    
    return result

if __name__ == "__main__":
    evaluate_stt()
```

### 예시 2: TTS 평가 스크립트

```python
# scripts/evaluate_tts.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from e2e_evaluation_pipeline.adapters.tts_adapter import TTSAdapter
from e2e_evaluation_pipeline.metrics.tts_metrics import evaluate_tts_from_adapter

def evaluate_tts():
    # TTS 어댑터 초기화
    tts_adapter = TTSAdapter(use_google=True)
    
    # 테스트 텍스트
    texts = [
        "카드 한도 상향 신청하고 싶어요",
        "결제일 변경 문의드립니다",
        "상담원 연결 부탁드립니다",
        "마이너스 통장 개설 가능한가요?",
        "적금 이자율이 얼마인가요?"
    ]
    
    # 평가 실행
    result = evaluate_tts_from_adapter(
        texts=texts,
        tts_adapter=tts_adapter,
        voice="ko-KR-Neural2-B",
        format="mp3"
    )
    
    # 결과 출력
    print(f"\nTTS Evaluation Results:")
    print(f"  Success Rate: {result.summary.get('success_rate', 0):.2f}%")
    print(f"  Average Synthesis Time: {result.summary.get('avg_synthesis_time_ms', 0):.2f}ms")
    print(f"  Average Chars/Second: {result.summary.get('avg_chars_per_second', 0):.2f}")
    print(f"  Error Rate: {result.summary.get('error_rate', 0):.2f}%")
    
    return result

if __name__ == "__main__":
    evaluate_tts()
```

### 예시 3: 의도분류 모델 평가 스크립트

```python
# scripts/evaluate_intent.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from e2e_evaluation_pipeline.metrics.intent_metrics import evaluate_intent_from_model

def evaluate_intent():
    # 모델 기반 평가
    result = evaluate_intent_from_model(
        test_data_path="e2e_evaluation_pipeline/datasets/intent_test/test_data.json",
        model_path=None  # 기본 경로 사용
    )
    
    # 결과 출력
    print(f"\nIntent Classification Evaluation Results:")
    print(f"  Accuracy: {result.summary.get('accuracy', 0):.2f}%")
    print(f"  Weighted F1: {result.summary.get('weighted_f1', 0):.2f}%")
    print(f"  HUMAN_REQUIRED Recall: {result.summary.get('human_required_recall', 0):.2f}%")
    
    return result

if __name__ == "__main__":
    evaluate_intent()
```

### 예시 4: RAG 검색 평가 스크립트

```python
# scripts/evaluate_rag.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_engine.vector_store import get_vector_store
from e2e_evaluation_pipeline.metrics.rag_metrics import evaluate_rag_from_golden_set

def evaluate_rag():
    # 벡터 스토어 초기화
    vector_store = get_vector_store()
    
    # Golden QA 셋 기반 평가
    result = evaluate_rag_from_golden_set(
        golden_qa_path="e2e_evaluation_pipeline/datasets/golden_qa/qa_set.json",
        vector_store=vector_store,
        top_k=3
    )
    
    # 결과 출력
    print(f"\nRAG Search Evaluation Results:")
    print(f"  Precision@3: {result.summary.get('avg_precision_at_3', 0):.2f}%")
    print(f"  MRR: {result.summary.get('avg_mrr', 0):.4f}")
    print(f"  NDCG@3: {result.summary.get('avg_ndcg_at_3', 0):.4f}")
    
    return result

if __name__ == "__main__":
    evaluate_rag()
```

## CI/CD 통합

GitHub Actions 예시:

```yaml
name: E2E Evaluation

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run E2E Evaluation (CI Mode)
        run: |
          python -m e2e_evaluation_pipeline --mode ci
      
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: evaluation-reports
          path: reports/
```

## KPI 우선순위

| 우선순위 | 설명 | 예시 |
|----------|------|------|
| **P0** | Critical - 반드시 통과해야 함 | HUMAN_REQUIRED Recall, Auto Resolution Rate |
| **P1** | High - 중요 품질 지표 | CER, Accuracy, ROUGE-L |
| **P2** | Medium - 참고 지표 | Top-3 Accuracy, BM25 Contribution |

## 산업 벤치마크

| 메트릭 | 목표 | 산업 벤치마크 | 출처 |
|--------|------|---------------|------|
| CER | ≤10% | 5-7% | Plivo, Retell AI |
| E2E Latency | ≤3s | ≤800ms | Plivo |
| FCR | ≥70% | 70-80% | Contact Center Industry |
| CSAT | ≥80% | 75-85% | Contact Center Industry |
| Auto Resolution | ≥40% | 60-80% | Gartner |

## 리포트 형식

평가 결과는 다음 형식으로 생성됩니다:

- **HTML**: 시각적 대시보드 형식 (`reports/evaluation_report.html`)
- **JSON**: 프로그래밍 처리용 (`reports/evaluation_report.json`)
- **Markdown**: 문서화용 (`reports/evaluation_report.md`)

## 주의사항

1. **환경 변수 설정**: STT/TTS API 키가 `.env` 파일에 설정되어 있어야 합니다.
2. **테스트 데이터 준비**: 각 모듈별 테스트 데이터를 `e2e_evaluation_pipeline/datasets/` 디렉토리에 준비해야 합니다.
3. **모델 경로**: 의도분류 모델이 `models/final_classifier_model/model_final/` 경로에 있어야 합니다.
4. **벡터 DB**: RAG 평가를 위해서는 벡터 DB가 초기화되어 있어야 합니다.

## 추가 리소스

- [E2E Evaluation Pipeline README](e2e_evaluation_pipeline/README.md)
- [KPI Thresholds 설정](e2e_evaluation_pipeline/configs/kpi_thresholds.py)
- [테스트 데이터 형식](e2e_evaluation_pipeline/datasets/)

## 질문 및 지원

평가 자동화 관련 질문이나 문제가 있으면 이슈를 등록하거나 팀에 문의하세요.

