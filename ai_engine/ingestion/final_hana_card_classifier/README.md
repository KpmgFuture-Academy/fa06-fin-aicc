# 카드사 고객센터 의도 분류 시스템

KcELECTRA 기반 LoRA Fine-tuning을 활용한 고객 문의 의도 분류 시스템입니다.

## 프로젝트 개요

- **모델**: KcELECTRA-base-v2022 + LoRA
- **카테고리**: 38개 분류
- **도메인**: 8개 (결제/청구, 한도/승인, 연체/수납, 대출, 포인트/혜택, 증명/세금, 공과금, 인증/보안/카드관리)
- **성능**: Accuracy 74.62%, Weighted F1 0.7420, Macro F1 0.6242

## 파일 구조

```
For_GitHub/
├── README.md                      # 이 파일
├── category_domain_mapping.json   # 38개 카테고리 → 8개 도메인 매핑
├── preprocessed_final/            # 전처리된 학습/검증 데이터
│   ├── train.json
│   ├── val.json
│   └── categories.txt
├── preprocess_data.py             # 데이터 전처리 스크립트
├── merge_labels_v2.py             # 라벨 병합 스크립트 (42→38 카테고리)
├── train_kcelectra_lora.py        # LoRA 학습 스크립트
├── analyze_confidence.py          # Confidence 분석 스크립트
├── intent_classifier.py           # 의도 분류기 추론 모듈
├── clarification_loop.py          # Clarification Loop 모듈 (Pattern B/C)
└── simple_rag.py                  # 간단한 RAG 테스트 모듈
```

## 주요 모듈

### 1. 의도 분류기 (intent_classifier.py)

```python
from intent_classifier import IntentClassifier

classifier = IntentClassifier(
    model_dir='./model_final',
    mapping_file='./category_domain_mapping.json'
)

# 분류 및 meta info 생성
meta_info = classifier.generate_meta_info("카드 결제대금 알려주세요")
print(meta_info['classification_result']['category_name'])  # 결제대금 안내
print(meta_info['classification_result']['confidence'])      # 0.95
print(meta_info['classification_result']['confidence_pattern'])  # A
```

### 2. Clarification Loop (clarification_loop.py)

Confidence Pattern에 따른 추가 질문 처리:
- **Pattern A** (confidence >= 0.9): 즉시 카테고리 확정
- **Pattern B** (0.5 <= confidence < 0.9): Clarification Loop 진입
- **Pattern C** (confidence < 0.5): Clarification Loop 진입

```python
from clarification_loop import ClarificationLoop
from intent_classifier import IntentClassifier

classifier = IntentClassifier(...)
loop = ClarificationLoop(
    classifier=classifier,
    max_turns=3,
    llm_model="gemma3:4b"  # Ollama 모델
)

result = loop.run("포인트 조회하고 싶어요")
```

### 3. Simple RAG (simple_rag.py)

도메인별 문서 기반 RAG 응답 생성:

```python
from simple_rag import SimpleRAG

rag = SimpleRAG(
    docs_dir='./Domain_Full_Templates',
    mapping_file='./category_domain_mapping.json',
    llm_model="gemma3:4b"
)

result = rag.generate_response(user_query, meta_info)
```

## Confidence Pattern

| Pattern | Confidence 범위 | 처리 방식 |
|---------|----------------|----------|
| A | >= 0.9 | 즉시 카테고리 확정 |
| B | 0.5 ~ 0.9 | Clarification Loop (최대 3회) |
| C | < 0.5 | Clarification Loop (최대 3회) |

## 도메인-카테고리 매핑

| 도메인 | 카테고리 수 | 주요 카테고리 |
|--------|------------|-------------|
| PAY_BILL (결제/청구) | 11 | 결제대금 안내, 가상계좌 안내, 이용내역 안내 |
| LIMIT_AUTH (한도/승인) | 5 | 한도 안내, 한도상향 접수/처리 |
| DELINQ (연체/수납) | 5 | 연체대금 안내, 선결제/즉시출금 |
| LOAN (대출) | 3 | 단기카드대출, 장기카드대출 |
| BENEFIT (포인트/혜택) | 6 | 포인트/마일리지 안내, 연회비 안내 |
| DOC_TAX (증명/세금) | 3 | 증명서/확인서 발급 |
| UTILITY (공과금) | 2 | 도시가스, 전화요금 |
| SEC_CARD (인증/보안) | 3 | 도난/분실 신청/해제 |

## 요구사항

```
torch>=2.0.0
transformers>=4.30.0
peft>=0.4.0
python-docx
requests
```

## 모델 파일

학습된 모델 파일은 용량이 크기 때문에 Google Drive에서 다운로드해야 합니다.
`model_final/` 폴더를 다운로드하여 프로젝트 루트에 배치하세요.

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 개발되었습니다.
