# BERT 금융보험 의도 분류 모델

한국어 BERT 기반 금융보험 고객 의도 분류 모델입니다.

## 모델 정보

- **기본 모델**: klue/bert-base (한국어 사전학습 BERT)
- **태스크**: 의도 분류 (Intent Classification)
- **클래스 수**: 3,623개
- **학습 데이터**: 133,042개 샘플
- **검증 데이터**: 23,479개 샘플
- **정확도**: 20.84% (랜덤 0.028% 대비 740배 향상)
- **F1 Score**: 14.79%

## 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/your-repo/financial-intent-bert.git
cd financial-intent-bert

# 라이브러리 설치
pip install -r requirements.txt
```

### 2. 모델 다운로드

**중요**: 모델 파일은 Git에 포함되지 않습니다 (435MB).

**다운로드**: [Google Drive](https://drive.google.com/drive/folders/14HhWnQG5GJjZi_9XMdPs6Vl8H-eUcuSf)

자세한 내용은 [MODEL_DOWNLOAD.md](MODEL_DOWNLOAD.md)를 참조하세요.

다운로드 후 다음 위치에 배치:
```
models/bert_intent_classifier/
├── model.safetensors (433MB)
├── config.json
├── id2intent.json
├── intent2id.json
└── tokenizer 파일들
```

### 3. 사용 방법

#### 대화형 모드 (추천)

```bash
python scripts/inference.py
```

#### 단일 텍스트 예측

```bash
python scripts/inference.py --text "신용카드 발급하고 싶어요"
```

#### Python 코드에서 사용

```python
from scripts.inference import IntentClassifier

# 분류기 초기화
classifier = IntentClassifier()

# 단일 예측
intent, confidence = classifier.predict_single("보험 청구하고 싶어요")
print(f"의도: {intent}, 신뢰도: {confidence:.2%}")

# Top-3 예측
results = classifier.predict("계좌 이체 문의", top_k=3)
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
- CUDA 지원 GPU (선택, CPU도 가능)

자세한 내용은 [requirements.txt](requirements.txt) 참조

## 프로젝트 구조

```
.
├── README.md                  # 이 파일
├── MODEL_DOWNLOAD.md          # 모델 다운로드 안내
├── requirements.txt           # 필수 라이브러리
├── .gitignore
│
├── scripts/
│   ├── inference.py          # 추론 스크립트
│   └── evaluate.py           # 평가 스크립트
│
├── models/                   # 모델 저장 위치 (수동 다운로드)
│   └── bert_intent_classifier/
│
└── outputs/                  # 평가 결과 저장
    ├── misclassified.csv
    └── evaluation_results.json
```

## 성능 지표

### 전체 성능
- **정확도**: 20.84%
- **F1 Score**: 14.79%
- **Precision**: 14.14%
- **Recall**: 20.84%

### 해석
- 3,623개 클래스에서 20.84% 정확도는 랜덤 예측(0.028%) 대비 **740배** 향상
- 클래스 불균형 문제 존재 (54%의 의도가 10개 이하 샘플)

## 개선 방향

1. **계층적 분류**: 4개 대분류 → 20-50개 중분류 → 상세 의도
2. **데이터 증강**: 소수 클래스 샘플 증가
3. **클래스 가중치**: 불균형 해소
4. **하이퍼파라미터 튜닝**: Learning rate, Batch size 조정
5. **앙상블**: 여러 모델 결합

## 문제 해결

### 모델을 찾을 수 없음
```
[ERROR] 모델을 찾을 수 없습니다
```

**해결**: [MODEL_DOWNLOAD.md](MODEL_DOWNLOAD.md)를 참조하여 모델 다운로드

### GPU 메모리 부족
```bash
# Batch size 줄이기
python scripts/evaluate.py --sample-size 1000
```

### 경로 오류
```python
# 직접 경로 지정
classifier = IntentClassifier(model_path='/path/to/model')
```

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 사용할 수 있습니다.

## 기여

버그 리포트 및 개선 제안은 이슈로 등록해주세요.

## 문의

프로젝트 관련 문의사항은 이슈 또는 이메일로 연락주세요.

---

**Last Updated**: 2025-11-18
**Version**: 1.0.0
