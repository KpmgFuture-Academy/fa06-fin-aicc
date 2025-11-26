# NLU Category Pipeline 구조 문서

## 개요

본 문서는 하나카드 NLU Category Pipeline v3의 상세 구조를 설명합니다.

---

## 1. 파이프라인 흐름

```
User Input
    │
    ▼
┌─────────────────┐
│  Preprocess     │  텍스트 정규화, 길이 검증
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Electra Model  │  카테고리 분류 (Temperature Scaling T=0.1)
│  (Category)     │  → category, confidence, top3
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Confidence     │  A/B/C 패턴 결정
│  Decision       │  → route_decision
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Pattern A  Pattern B/C
 (≥10%)     (<10%)
    │         │
    │         ▼
    │    ┌────────────────┐
    │    │ Clarification  │ ◄─── 최대 3회 반복
    │    │ Loop           │
    │    └───────┬────────┘
    │            │
    │       ┌────┴────┐
    │       │         │
    │       ▼         ▼
    │   Pattern A  Max Retry
    │   (조기종료)  (3회 도달)
    │       │         │
    │       │         ▼
    │       │    ┌──────────┐
    │       │    │LLM Refine│
    │       │    └────┬─────┘
    │       │         │
    └───────┴─────────┘
            │
            ▼
    ┌─────────────────┐
    │ Final           │
    │ Classification  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │     RAG         │  관련 문서 검색
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   LLM Answer    │  최종 응답 생성
    └────────┬────────┘
             │
             ▼
         Output
```

---

## 2. Confidence Threshold 정책

### 2.1 임계값 상수

```python
# nodes_confidence.py

CONF_THRESHOLD_A_SHORT: float = 0.10  # 10% 이상 → Pattern A
CONF_THRESHOLD_B_SHORT: float = 0.05  # 5% 이상 → Pattern B
MAX_CLARIFY_RETRY: int = 3            # 최대 재질문 횟수
```

### 2.2 패턴 분류

| Pattern | 조건 | 라우팅 | 설명 |
|---------|------|--------|------|
| A | `confidence ≥ 0.10` | `high_conf` | 고신뢰 - 바로 최종 분류 |
| B | `0.05 ≤ confidence < 0.10` | `need_clarify` | 중신뢰 - Clarification 필요 |
| C | `confidence < 0.05` | `need_clarify` | 저신뢰 - Clarification 필요 |

### 2.3 라우팅 함수

```python
def determine_route(confidence_pattern: str) -> Literal["high_conf", "need_clarify"]:
    if confidence_pattern == "A":
        return "high_conf"
    else:
        return "need_clarify"
```

---

## 3. Clarification Loop

### 3.1 개념

저신뢰 분류(Pattern B/C) 시, 고객에게 추가 질문을 하여 의도를 명확히 파악하는 과정입니다.

### 3.2 흐름

1. **need_clarify 진입**: Pattern B/C로 분류됨
2. **질문 생성**: LLM이 모호한 부분에 대해 질문 생성
3. **고객 응답**: 고객의 추가 답변 수신
4. **effective_query 구성**: 원본 질문 + 모든 답변 연결
5. **Electra 재분류**: effective_query로 다시 분류
6. **조기 종료**: Pattern A 도달 시 즉시 종료
7. **최대 횟수 도달**: 3회 시 LLM Refine으로 최종 결정

### 3.3 Conversation 구조

```python
class Conversation(TypedDict):
    original_query: str           # 원본 질문
    clarify_turns: list[ClarifyTurn]  # 재질문/답변 이력
    retry_count: int              # 현재 재시도 횟수
    max_retry: int                # 최대 재시도 횟수 (3)

class ClarifyTurn(TypedDict):
    q: str  # LLM이 물어본 질문
    a: str  # 고객 답변
```

### 3.4 effective_query 생성

```python
def build_effective_query(conversation: Conversation) -> str:
    """원본 질문 + 모든 답변을 연결"""
    parts = [conversation["original_query"]]
    for turn in conversation["clarify_turns"]:
        parts.append(turn["a"])
    return " ".join(parts)
```

---

## 4. LLM Refine

### 4.1 역할

Clarification Loop 최대 횟수(3회) 도달 시, LLM이 top3 후보 중 최종 카테고리를 선택합니다.

### 4.2 입력

- `effective_query`: 원본 + 모든 답변 연결
- `electra_top3`: Electra의 상위 3개 예측

### 4.3 출력

```python
class LLMRefineResult(TypedDict):
    selected_category: str    # 선택된 카테고리
    confidence: float         # LLM 신뢰도
    reason: str              # 선택 이유
    meta: dict               # 메타데이터
```

---

## 5. 주요 모듈

### 5.1 nodes_confidence.py

- `compute_confidence_pattern()`: A/B/C 패턴 계산
- `determine_route()`: 라우팅 결정
- `confidence_decision_node()`: 메인 노드 함수

### 5.2 conversation_utils.py

- `create_conversation()`: 대화 구조 생성
- `add_clarify_turn()`: 턴 추가
- `build_effective_query()`: effective_query 생성

### 5.3 llm_clarify.py

- `LLMClarifyService`: Clarification 서비스
- `MockLLMClarifier`: 테스트용 Mock
- `ClaudeLLMClarifier`: 실제 Claude API

### 5.4 llm_refine.py

- `LLMRefineService`: Refine 서비스
- `refine()`: effective_query 기반 최종 결정
- `refine_from_conversation()`: Conversation 객체 기반

### 5.5 graph_builder.py

- `build_graph()`: LangGraph 그래프 빌드
- `run_clarification_loop()`: Clarification 루프 실행
- `clarification_loop_node()`: 루프 노드
- `final_classification_node()`: 최종 분류 노드

---

## 6. Temperature Scaling

### 6.1 개념

Electra 모델의 softmax 출력에 Temperature를 적용하여 확률 분포를 조정합니다.

### 6.2 공식

```
scaled_logits = logits / T
probs = softmax(scaled_logits)
```

- `T < 1`: 확률 분포가 더 sharp해짐 (확신도 증가)
- `T > 1`: 확률 분포가 더 smooth해짐 (불확실성 증가)

### 6.3 현재 설정

```python
TEMPERATURE = 0.1  # 매우 sharp한 분포
```

---

## 7. State 구조

### 7.1 PipelineState

```python
class PipelineState(TypedDict, total=False):
    # 입력
    user_input: str

    # Electra 결과
    category: str
    confidence: float
    top3: list[Top3Item]

    # Confidence Decision
    confidence_pattern: str  # "A", "B", "C"
    route_decision: str      # "high_conf", "need_clarify"

    # Clarification
    conversation: Conversation
    clarify_loop_history: list[dict]

    # Final
    final_category: str
    final_confidence: float
    llm_refined: bool
    refine_reason: str

    # RAG
    rag_docs: list[RAGDocument]

    # LLM Answer
    answer: str

    # Metadata
    metadata: PipelineMetadata
```

---

## 8. 버전 히스토리

| 버전 | 주요 변경 |
|------|----------|
| v3.0.0 | Clarification Loop 추가, Confidence Threshold 상수화 |
| v2.0.0 | LLM Refine 파이프라인 추가 |
| v1.0.0 | 초기 릴리스 (Electra + RAG) |
