# IntentType vs TriageDecisionType 분석

## 📋 개요

두 Enum의 목적과 사용 패턴을 분석하여 통합 가능성을 검토합니다.

---

## 🔍 Enum 정의

### 1. IntentType (7-10줄)
```python
class IntentType(str, Enum):   # 챗봇 의도 타입
    INFO_REQ = "INFO_REQ"      # 정보 요청
    COMPLAINT = "COMPLAINT"    # 민원
    HUMAN_REQ = "HUMAN_REQ"    # 상담원 연결 요청
```

### 2. TriageDecisionType (21-24줄)
```python
class TriageDecisionType(str, Enum):  # Triage 에이전트 의사결정 타입
    AUTO_HANDLE_OK = "AUTO_HANDLE_OK"      # 자동 처리 가능 (답변 생성)
    NEED_MORE_INFO = "NEED_MORE_INFO"     # 추가 정보 필요 (질문 생성)
    HUMAN_REQUIRED = "HUMAN_REQUIRED"      # 상담사 연결 필요
```

---

## 🎯 역할 차이점

### IntentType: **고객의 의도/감정 상태**
- **목적**: 고객이 무엇을 원하는지 분류
- **관점**: 고객 중심 (Customer-facing)
- **사용 위치**: 
  - API 응답 (`ChatResponse.intent`) - 클라이언트에 전달
  - DB 저장 (`chat_message.intent`) - 분석/통계용
  - 프론트엔드 표시 (의도별 UI 표시)

### TriageDecisionType: **시스템의 처리 결정**
- **목적**: 시스템이 어떻게 처리할지 결정
- **관점**: 시스템 중심 (System-internal)
- **사용 위치**:
  - 워크플로우 분기 (`workflow.py`의 `_route_after_triage`)
  - `answer_agent` 내부 로직 분기 (답변 생성 방식 결정)
  - 내부 상태 관리 (`GraphState.triage_decision`)

---

## 📊 매핑 관계

코드 분석 결과, 두 Enum은 **1:1 매핑이 아닙니다**:

| TriageDecisionType | IntentType | 조건 |
|-------------------|-----------|------|
| `AUTO_HANDLE_OK` | `INFO_REQ` | 항상 |
| `NEED_MORE_INFO` | `INFO_REQ` | 항상 |
| `HUMAN_REQUIRED` | `COMPLAINT` | 민원 키워드 감지 시 |
| `HUMAN_REQUIRED` | `HUMAN_REQ` | 그 외 상담원 연결 요청 |

**코드 위치**: `triage_agent.py` (206-223줄)

```python
if "AUTO_HANDLE_OK" in llm_response:
    triage_decision = TriageDecisionType.AUTO_HANDLE_OK
    intent_type = IntentType.INFO_REQ  # ← 항상 INFO_REQ
elif "NEED_MORE_INFO" in llm_response:
    triage_decision = TriageDecisionType.NEED_MORE_INFO
    intent_type = IntentType.INFO_REQ  # ← 항상 INFO_REQ
elif "HUMAN_REQUIRED" in llm_response:
    triage_decision = TriageDecisionType.HUMAN_REQUIRED
    # ← 조건부 분기
    if is_complaint:
        intent_type = IntentType.COMPLAINT
    else:
        intent_type = IntentType.HUMAN_REQ
```

---

## 🔄 사용 흐름

```
1. triage_agent
   ├─ TriageDecisionType 결정 (시스템 처리 방식)
   └─ IntentType 결정 (고객 의도 분류)
   
2. answer_agent
   └─ TriageDecisionType 기반으로 답변 생성 방식 결정
      ├─ AUTO_HANDLE_OK → RAG 기반 답변 생성
      ├─ NEED_MORE_INFO → 추가 질문 생성
      └─ HUMAN_REQUIRED → 상담사 연결 안내
   
3. workflow_service
   ├─ TriageDecisionType → ActionType 변환 (내부 로직)
   └─ IntentType → ChatResponse.intent (API 응답)
```

---

## ❌ 통합 시 문제점

### 1. 의미론적 차이
- `IntentType`: "고객이 무엇을 원하는가?" (What does the customer want?)
- `TriageDecisionType`: "시스템이 어떻게 처리할 것인가?" (How should the system handle it?)

### 2. 매핑 불일치
- `TriageDecisionType.HUMAN_REQUIRED` → `IntentType.COMPLAINT` 또는 `IntentType.HUMAN_REQ`
- 하나의 TriageDecisionType이 여러 IntentType으로 매핑될 수 있음

### 3. 사용 목적 차이
- `IntentType`: 외부 API 응답, DB 저장, 프론트엔드 표시
- `TriageDecisionType`: 내부 워크플로우 분기, 답변 생성 로직

### 4. 확장성 문제
- 향후 `IntentType`에 새로운 의도 추가 시 (예: `INQUIRY`, `FEEDBACK`)
- `TriageDecisionType`에 새로운 처리 방식 추가 시 (예: `ESCALATE`, `DEFER`)
- 통합 시 변경 영향 범위가 커짐

---

## ✅ 분리 유지 권장 사유

### 1. **관심사의 분리 (Separation of Concerns)**
- 고객 의도 분류와 시스템 처리 결정은 서로 다른 책임
- 각각 독립적으로 변경 가능해야 함

### 2. **API 계약 유지**
- `ChatResponse.intent`는 클라이언트와의 계약
- 내부 처리 로직 변경이 API 응답 형식에 영향을 주면 안 됨

### 3. **유지보수성**
- 각 Enum의 목적이 명확하여 코드 가독성 향상
- 변경 시 영향 범위가 명확함

### 4. **확장성**
- 새로운 의도 타입 추가 시 IntentType만 수정
- 새로운 처리 방식 추가 시 TriageDecisionType만 수정

---

## 💡 결론

**두 Enum을 통합하지 않는 것이 올바른 설계입니다.**

### 현재 구조의 장점:
1. ✅ 명확한 책임 분리
2. ✅ 독립적인 확장 가능
3. ✅ API 계약 보호
4. ✅ 코드 가독성 향상

### 만약 통합한다면:
- ❌ 의미론적 혼란 (고객 의도 vs 시스템 결정)
- ❌ 매핑 로직 복잡도 증가
- ❌ API 변경 필요 (클라이언트 영향)
- ❌ 유지보수 어려움

---

## 📝 참고: 현재 사용 파일

### IntentType 사용:
- `triage_agent.py` - 의도 분류
- `state.py` - GraphState 정의
- `workflow_service.py` - API 응답 생성
- `chat.py` - ChatResponse 스키마
- `chat_message.py` - DB 모델
- 프론트엔드 (`api.ts`, `ChatMessage.tsx`)

### TriageDecisionType 사용:
- `triage_agent.py` - 처리 결정
- `answer_agent.py` - 답변 생성 분기
- `workflow.py` - 워크플로우 라우팅
- `state.py` - GraphState 정의
- `workflow_service.py` - ActionType 변환

