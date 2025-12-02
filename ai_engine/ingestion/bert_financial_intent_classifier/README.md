# Final Classifier 의도 분류 모델

LoRA 기반 KcELECTRA 금융 고객 의도 분류 모델입니다.

## 모델 정보

- **기본 모델**: beomi/KcELECTRA-base-v2022
- **Fine-tuning 방식**: LoRA (Low-Rank Adaptation)
- **태스크**: 의도 분류 (Intent Classification)
- **카테고리 수**: 38개
- **도메인 수**: 8개
- **정확도**: 74.62%
- **Weighted F1 Score**: 0.7420
- **Macro F1 Score**: 0.6242

## 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/your-repo/financial-intent-bert.git
cd financial-intent-bert

# 라이브러리 설치
pip install -r requirements.txt
```

### 2. 모델 배치

모델 파일을 다음 위치에 배치:
```
models/final_classifier_model/model_final/
├── best_model.pt              # 최고 성능 체크포인트 (~500MB)
├── latest_checkpoint.pt       # 최신 체크포인트 (~500MB)
├── evaluation_results.txt     # 상세 평가 결과
├── confidence_analysis.json   # Confidence 분석 결과
└── lora_adapter/              # LoRA 어댑터 (경량)
    ├── adapter_config.json
    ├── adapter_model.safetensors (~4MB)
    └── README.md
```

### 3. 사용 방법

#### 대화형 모드 (추천)

```bash
python scripts/inference.py
```

#### 단일 텍스트 예측

```bash
python scripts/inference.py --text "카드 한도 상향하고 싶어요"
```

#### Python 코드에서 사용

```python
from scripts.inference import IntentClassifier

# 분류기 초기화
classifier = IntentClassifier()

# 단일 예측
intent, confidence = classifier.predict_single("카드 한도 상향하고 싶어요")
print(f"의도: {intent}, 신뢰도: {confidence:.2%}")

# Confidence 패턴 확인
pattern = classifier.get_confidence_pattern(confidence)
print(f"Pattern: {pattern}")  # A(고신뢰), B(중신뢰), C(저신뢰)

# Top-3 예측
results = classifier.predict("결제일 변경 문의", top_k=3)
for result in results:
    print(f"{result['intent']}: {result['confidence']:.2%}")
```

## 모델 평가

검증 데이터로 모델 성능을 평가하려면:

```bash
python scripts/evaluate.py
```

출력:
- 전체 정확도
- Classification Report
- 오분류 분석 (misclassified.csv)
- 평가 결과 (evaluation_results.json)

## 요구사항

- Python 3.8+
- PyTorch 2.1.0+
- transformers 4.36.0+
- peft 0.4.0+ (LoRA 어댑터 로드용)
- CUDA 지원 GPU (선택, CPU도 가능하나 느림)

자세한 내용은 프로젝트 루트의 [requirements.txt](../../../requirements.txt) 참조

## 프로젝트 구조

```
fa06-fin-aicc/
├── ai_engine/ingestion/bert_financial_intent_classifier/
│   ├── README.md              # 이 파일
│   ├── MODEL_DOWNLOAD.md      # 모델 다운로드 안내
│   ├── requirements.txt       # 필수 라이브러리
│   └── scripts/
│       ├── inference.py       # 추론 스크립트
│       └── evaluate.py        # 평가 스크립트
│
└── models/
    └── final_classifier_model/
        └── model_final/       # 모델 저장 위치
            ├── best_model.pt
            ├── lora_adapter/
            └── ...
```

## 성능 지표

### 전체 성능
- **정확도**: 74.62%
- **Weighted F1 Score**: 0.7420
- **Macro F1 Score**: 0.6242

### Confidence Pattern 기준
- **Pattern A** (>=0.9): 고신뢰 - 즉시 확정
- **Pattern B** (0.5~0.9): 중신뢰 - Clarification 필요
- **Pattern C** (<0.5): 저신뢰 - Clarification 필요

### 해석
- 38개 카테고리, 8개 도메인으로 구조화된 분류 체계
- LoRA 방식으로 효율적인 파인튜닝 (전체 모델 대비 1% 미만 파라미터 학습)

## 문제 해결

### 모델을 찾을 수 없음
```
[ERROR] 모델을 찾을 수 없습니다
```

**해결**: 모델을 `models/final_classifier_model/model_final/` 경로에 배치

### peft 라이브러리 오류
```bash
# peft 설치
pip install peft>=0.4.0
```

### GPU 메모리 부족
- GPU 메모리 최소 4GB 권장
- CPU에서도 동작하나 추론 속도가 느릴 수 있음

### 경로 오류
```python
# 직접 경로 지정
classifier = IntentClassifier(model_path='/path/to/model_final')
```

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 사용할 수 있습니다.

## 기여

버그 리포트 및 개선 제안은 이슈로 등록해주세요.

## 문의

프로젝트 관련 문의사항은 이슈 또는 이메일로 연락주세요.

---

**Last Updated**: 2025-12-02
**Version**: 2.0.0 (Final Classifier with LoRA)
