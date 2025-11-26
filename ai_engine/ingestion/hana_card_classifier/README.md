# 📘 Hana Card NLU Category Pipeline

고객 상담 텍스트를 자동으로 분석하고, 정확한 카테고리로 분류하며, 필요한 경우 Clarification Loop와 RAG 기반 답변 생성을 수행하는 **하나카드 NLU 파이프라인 프로젝트**입니다.

---

# 📑 목차

1. 프로젝트 소개  
2. 전체 파이프라인 구조 (v3)  
3. Confidence Threshold & Routing  
4. Clarification Loop 동작 방식  
5. 설치 및 환경 준비  
6. 모델 다운로드  
7. 사용 방법  
8. 테스트 실행  
9. 프로젝트 폴더 구조  
10. 핵심 모듈 설명  
11. Version History  
12. 라이선스  

---

# 🔍 프로젝트 소개

하나카드 고객센터로 들어오는 상담 문장을 자동으로 이해하고 다음 기능을 수행합니다:

### ✔ Electra 기반 분류  
Fine-tuned KoELECTRA 기반 42개 카테고리 분류 모델 사용

### ✔ Clarification Loop (v3)
Electra Confidence가 일정 기준보다 낮으면  
→ LLM이 고객에게 재질문  
→ 고객 답변 반영하여 재분류  
→ 최대 3회 반복

### ✔ LLM Refine  
최종 카테고리가 불확실할 때 Claude 기반 규칙+LLM 재분류

### ✔ RAG 검색  
최종 카테고리에 따라 내부 문서 검색 수행

### ✔ LLM Answer  
최종 고객 응대 문장을 생성

---

# 🧠 전체 파이프라인 구조 (v3)

```
User Input
    │
    ▼
Electra Model (T=0.1)
    │
Confidence Decision
    ├── Pattern A (≥10%) → Final Classification
    └── Pattern B/C (<10%) → Clarification Loop (≤3 turns)
                                   │
                                   ├── Pattern A 조기 종료
                                   └── Pattern B/C 지속
    │
Final Classification (Electra or LLM Refine)
    │
RAG → LLM Answer → Output
```

---

# 🎯 Confidence Threshold & Routing

| Pattern | 조건 | 경로 | 설명 |
|--------|-------|--------|--------|
| **A** | confidence ≥ 10% | high_conf → Final | 고신뢰 → Clarify 생략 |
| **B** | 5% ≤ conf < 10% | need_clarify | 중신뢰 → Clarify |
| **C** | conf < 5% | need_clarify | 저신뢰 → Clarify |

---

# 🔁 Clarification Loop 동작 방식

LLM이 고객에게 “추가 설명 요청”하는 방식으로 정확도 상승 유도:

1. LLM이 Clarifying Question 생성  
2. 고객 응답 (Mock 또는 실제 대화)  
3. `effective_query = original + clarifications`  
4. Electra로 재분류  
5. Pattern A 도달 시 조기 종료  
6. 3회 반복 시 LLM Refine 수행 후 종료

---

# 🛠 설치 및 환경 준비

```bash
git clone https://github.com/your-org/Hana_Card_GitHub
cd Hana_Card_GitHub
pip install -r requirements.txt
```

---

# 📦 모델 다운로드

> ⚠ **모델은 용량 문제로 GitHub에 포함되지 않습니다.**

아래 파일들을 Google Drive에서 다운로드해야 합니다:

## Electra Category Classifier 모델  
필수 다운로드 파일:

```
models/
└── consulting_category_classifier_v2_aug_fusion/
    ├── config.json
    ├── model.safetensors
    ├── vocab.txt
    ├── tokenizer.json
    ├── tokenizer_config.json
    └── special_tokens_map.json
```

🔗 **Google Drive 링크 (업로드 예정)**  
https://drive.google.com/XXXXXX

---

# ▶ 사용 방법

### 기본 실행

```python
from nlu_category import run_pipeline

result = run_pipeline("카드 한도 올려주세요")
print(result["final_category"])
print(result["answer"])
```

### Clarification Loop 테스트 (Mock)

```python
run_pipeline(
   "카드 문의",
   mock_mode=True,
   mock_answers=["한도 문의입니다", "상향하고 싶어요"],
   verbose=True
)
```

### 실제 LLM Refine 사용

```python
run_pipeline("카드 한도 올려주세요", mock_mode=False)
```

---

# 🧪 테스트 실행

### Windows

```bash
scripts\run_tests.bat
scripts\run_tests.bat --real-api
scripts\run_tests.bat -v
```

### Linux / Mac

```bash
chmod +x scripts/run_tests.sh
./scripts/run_tests.sh
./scripts/run_tests.sh --real-api -v
```

또는 Python 직접 실행:

```bash
python -m examples.test_llm_refine_pipeline
```

---

# 📁 프로젝트 폴더 구조

```
Hana_Card_GitHub/
├── README.md
├── requirements.txt
├── test_queries.txt
├── nlu_category/
│   ├── model_service_electra.py
│   ├── llm_clarify.py
│   ├── llm_refine.py
│   ├── conversation_utils.py
│   ├── graph_builder.py
│   ├── nodes_*.py
│   └── utils/
├── examples/
│   ├── test_llm_refine_pipeline.py
│   ├── test_clarify_only.py
│   └── test_refine_only.py
└── scripts/
    ├── run_tests.bat
    └── run_tests.sh
```

---

# 🧩 주요 모듈 설명

| 모듈 | 설명 |
|------|------|
| model_service_electra | Electra 분류 모델 |
| llm_clarify | Clarifying 질문 생성 |
| conversation_utils | effective_query 구성 |
| llm_refine | 규칙+LLM 기반 최종 보정 |
| graph_builder | 전체 파이프라인 구성 |
| nodes_confidence | Confidence 패턴 판단 |

---

# 📌 Version History

| 버전 | 변경 내용 |
|-------|-------------|
| v3.0.0 | Clarification Loop 추가, Pattern A/B/C 기준 적용 |
| v2.0.0 | LLM Refine 추가 |
| v1.0.0 | Electra + RAG 최초 버전 |

---

# 📄 라이선스

MIT License
