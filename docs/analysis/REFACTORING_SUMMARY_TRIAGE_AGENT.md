# Triage Agent 리팩토링 및 정보 수집 단계 구현 - 수정사항 정리

## 📋 개요

이번 수정은 챗봇의 의사결정 프로세스를 개선하고, 상담사 연결 전 정보 수집 단계를 구현한 대규모 리팩토링입니다.

**주요 변경사항:**
- `decision_agent` → `triage_agent`로 노드명 변경
- Triage Decision Type 도입 (AUTO_HANDLE_OK, NEED_MORE_INFO, HUMAN_REQUIRED)
- LLM 기반 종합 판단 로직으로 전환
- 상담사 연결 전 정보 수집 단계 구현 (5회 질문 + 6번째 연결 안내)

---

## 🔄 변경된 파일 목록

### 1. 스키마 및 타입 정의
- `app/schemas/common.py` - TriageDecisionType Enum 추가

### 2. 상태 정의
- `ai_engine/graph/state.py` - 정보 수집 관련 필드 추가 및 주석 업데이트

### 3. 노드 파일
- `ai_engine/graph/nodes/triage_agent.py` (기존 `decision_agent.py`에서 이름 변경)
- `ai_engine/graph/nodes/answer_agent.py` - triage_decision 기반 분기 처리

### 4. 워크플로우
- `ai_engine/graph/workflow.py` - 라우팅 로직 수정

### 5. 서비스 레이어
- `app/services/workflow_service.py` - 상태 복원 로직 및 suggested_action 우선순위 수정

### 6. 기타
- `ai_engine/graph/tools/__init__.py` - 주석 업데이트
- `ai_engine/graph/nodes/chat_db_storage.py` - 주석 수정

---

## 📝 상세 수정 내용

### 1. Triage Decision Type 정의

**파일:** `app/schemas/common.py`

**추가된 Enum:**
```python
class TriageDecisionType(str, Enum):  # Triage 에이전트 의사결정 타입
    AUTO_HANDLE_OK = "AUTO_HANDLE_OK"      # 자동 처리 가능 (답변 생성)
    NEED_MORE_INFO = "NEED_MORE_INFO"     # 추가 정보 필요 (질문 생성)
    HUMAN_REQUIRED = "HUMAN_REQUIRED"      # 상담사 연결 필요
```

**의미:**
- `AUTO_HANDLE_OK`: RAG 문서 기반으로 답변 생성 가능
- `NEED_MORE_INFO`: 추가 정보가 필요하여 질문 생성
- `HUMAN_REQUIRED`: 상담사 연결 필요

---

### 2. 노드명 변경: decision_agent → triage_agent

**변경된 파일:**
- `ai_engine/graph/nodes/decision_agent.py` → `triage_agent.py` (파일명은 사용자가 직접 변경)
- 함수명: `decision_agent_node` → `triage_agent_node`

**참조 업데이트:**
- `ai_engine/graph/workflow.py`
- `ai_engine/graph/nodes/answer_agent.py`
- `ai_engine/graph/state.py`
- `ai_engine/graph/tools/__init__.py`
- `app/services/workflow_service.py`

---

### 3. GraphState 필드 추가

**파일:** `ai_engine/graph/state.py`

**추가된 필드:**
```python
# ========== 정보 수집 단계 관련 ==========
is_collecting_info: bool  # 정보 수집 단계 여부 (False: 일반 대화, True: 정보 수집 중)
info_collection_count: int  # 정보 수집 질문 횟수 (0~6, 6회 도달 시 summary_agent로 이동)

# ========== 판단 에이전트 노드 (triage_agent) ==========
triage_decision: Optional[TriageDecisionType]  # Triage 의사결정 결과
```

**주요 변경사항:**
- 상단 주석에 새로운 워크플로우 구조 반영
- 정보 수집 단계 플로우 설명 추가

---

### 4. triage_agent_node 대폭 개선

**파일:** `ai_engine/graph/nodes/triage_agent.py`

#### 4.1 주요 변경사항

**이전:**
- 유사도 점수 기반 규칙 로직
- 키워드 기반 개인화/민원 감지
- 하드코딩된 임계값 사용

**변경 후:**
- `intent_classification_tool`과 `rag_search_tool` 직접 호출
- LLM 기반 종합 판단 (문서 내용 전체 분석)
- 문서 내용의 관련성과 완전성을 기준으로 판단

#### 4.2 처리 흐름

```
1. 직접 상담원 연결 요청 감지 (키워드/패턴 매칭)
   → HUMAN_REQUIRED 반환 (Tool 사용 안 함)

2. 정보 수집 단계 확인
   → is_collecting_info=True면 Tool 사용 안 하고 NEED_MORE_INFO 반환

3. Tool 호출
   → intent_classification_tool: 문맥 의도 분류
   → rag_search_tool: 관련 문서 검색 (상위 5개)

4. LLM 판단
   → 검색된 문서의 전체 내용을 분석
   → AUTO_HANDLE_OK / NEED_MORE_INFO / HUMAN_REQUIRED 결정
```

#### 4.3 LLM 프롬프트 개선

**변경 전:**
- 유사도 점수만 참고
- 문서 내용 일부만 포함 (100자, 상위 3개)

**변경 후:**
- 문서 전체 내용 포함 (상위 5개)
- 유사도 점수는 참고용, 문서 내용이 핵심
- 명확한 판단 기준 제시

**System 메시지 핵심 내용:**
```
- 검색된 문서의 실제 내용을 꼼꼼히 읽고 분석
- 유사도 점수는 참고용일 뿐, 실제 문서 내용이 핵심
- 문서 내용만으로 답변이 가능하면 AUTO_HANDLE_OK
- 부분적으로만 가능하면 NEED_MORE_INFO
- 불가능하면 HUMAN_REQUIRED
```

#### 4.4 제거된 로직

- ❌ `is_personalized_query` 키워드 감지 (개인화된 질문)
- ❌ `is_complaint` 키워드 감지 (민원)
- ❌ 하드코딩된 유사도 임계값 (`SIMILARITY_THRESHOLD_HIGH`, `SIMILARITY_THRESHOLD_LOW`)

**이유:** LLM에 모든 판단을 위임하여 더 정확하고 맥락적인 판단 가능

---

### 5. answer_agent_node 분기 처리 개선

**파일:** `ai_engine/graph/nodes/answer_agent.py`

#### 5.1 triage_decision 기반 분기

**이전:** 단일 답변 생성 로직

**변경 후:** `triage_decision` 값에 따라 3가지 방식으로 처리

```python
if triage_decision == TriageDecisionType.HUMAN_REQUIRED:
    # 상담사 연결 안내 또는 정보 수집 시작
elif triage_decision == TriageDecisionType.NEED_MORE_INFO:
    # 추가 정보 요청 질문 생성
elif triage_decision == TriageDecisionType.AUTO_HANDLE_OK:
    # RAG 문서 기반 답변 생성
```

#### 5.2 HUMAN_REQUIRED 처리

**케이스 1: 첫 번째 상담사 연결 제안**
```
AI: "상담사가 필요한 업무입니다. 상담사 연결하시겠습니까?"
```

**케이스 2: 사용자 긍정 응답**
```
사용자: "예" / "연결해주세요" 등
AI: "상담사 연결 전, 빠른 업무 처리를 도와드리기 위해 추가적인 질문을 드리겠습니다."
→ is_collecting_info = True, info_collection_count = 0
```

**케이스 3: 사용자 부정 응답**
```
사용자: "아니요" / "필요없어" 등
AI: "상담사를 연결하지 않아 상담이 종료됩니다."
```

#### 5.3 NEED_MORE_INFO 처리 (정보 수집 단계)

**1~5번째 질문:**
- LLM을 통해 추가 정보 요청 질문 생성
- `info_collection_count` 증가 (1 → 2 → 3 → 4 → 5)
- `chat_db_storage`로 이동

**6번째 턴:**
- 질문 생성 대신 고정 메시지 출력
- `info_collection_count = 6`
- `summary_agent`로 이동

```python
if is_collecting and current_count >= 6:
    state["ai_message"] = "상담사 연결 예정입니다. 잠시만 기다려주세요."
    return state  # summary_agent로 이동
```

#### 5.4 프롬프트 헬퍼 함수 분리

**추가된 함수:**
- `_create_question_generation_prompt()`: NEED_MORE_INFO용 프롬프트
- `_create_answer_generation_prompt()`: AUTO_HANDLE_OK용 프롬프트

**효과:** 코드 가독성 향상, 유지보수 용이

---

### 6. workflow.py 라우팅 로직 수정

**파일:** `ai_engine/graph/workflow.py`

#### 6.1 변경된 라우팅 함수

**이전:** `_route_after_decision`
**변경 후:** `_route_after_triage`

**변경 내용:**
- 모든 `triage_decision` 결과가 `answer_agent`로 이동
- `answer_agent` 내부에서 `triage_decision`에 따라 처리

#### 6.2 새로운 라우팅 함수 추가

**`_route_after_answer` 함수:**
```python
def _route_after_answer(state: GraphState) -> str:
    """answer_agent 이후 분기.
    
    정보 수집 6번째 턴 (고정 메시지 출력 후) summary_agent로 이동,
    그 외에는 chat_db_storage로 이동.
    """
    info_collection_count = state.get("info_collection_count", 0)
    
    # 6번째 턴 (고정 메시지 출력 후, count >= 6) summary_agent로 이동
    if info_collection_count >= 6:
        return "summary_agent"  # 정보 수집 완료 → 요약
    return "chat_db_storage"  # 일반 케이스 (1~5번째 질문 또는 일반 대화)
```

#### 6.3 워크플로우 그래프 구조

```
triage_agent
  ↓
answer_agent
  ↓ (조건부 분기)
  ├─ info_collection_count >= 6 → summary_agent → human_transfer → chat_db_storage → END
  └─ 그 외 → chat_db_storage → END
```

---

### 7. workflow_service.py 상태 관리 개선

**파일:** `app/services/workflow_service.py`

#### 7.1 정보 수집 상태 복원 함수 추가

**`_restore_info_collection_state` 함수:**
```python
def _restore_info_collection_state(conversation_history: list[ConversationMessage]) -> tuple[bool, int]:
    """conversation_history를 분석하여 정보 수집 상태 복원
    
    Returns:
        tuple[bool, int]: (is_collecting_info, info_collection_count)
    """
```

**로직:**
1. "상담사 연결 예정입니다" 메시지 확인 → 상태 리셋 (False, 0)
2. "추가적인 질문을 드리겠습니다" 메시지 확인 → 정보 수집 시작 (True, 0)
3. 이후 질문 패턴 카운트 → `info_collection_count` 추정

**이유:** Option B 방식 (DB 스키마 변경 없이 conversation_history 분석)

#### 7.2 chat_request_to_state 수정

**추가된 로직:**
```python
# conversation_history를 분석하여 정보 수집 상태 복원
is_collecting_info, info_collection_count = _restore_info_collection_state(conversation_history)

state: GraphState = {
    ...
    "is_collecting_info": is_collecting_info,  # conversation_history에서 복원
    "info_collection_count": info_collection_count,  # conversation_history에서 복원
}
```

**효과:** 정보 수집 상태가 턴 간에 유지됨

#### 7.3 state_to_chat_response 수정

**변경 전:**
- 항상 `triage_decision`과 `requires_consultant`로 `suggested_action` 결정
- `human_transfer` 노드에서 설정한 `HANDOVER`가 덮어씌워짐

**변경 후:**
```python
# state에 이미 설정된 suggested_action이 있으면 우선 사용
suggested_action = state.get("suggested_action")

if suggested_action is None:
    # suggested_action이 설정되지 않은 경우에만 결정
    # triage_decision과 requires_consultant 기반 로직
```

**효과:** `human_transfer` 노드에서 설정한 `HANDOVER`가 올바르게 반영됨

#### 7.4 process_handover 수정

**추가된 필드:**
```python
initial_state: GraphState = {
    ...
    "is_collecting_info": False,  # 상담원 이관 요청은 정보 수집과 별개
    "info_collection_count": 0,  # 상담원 이관 요청은 정보 수집과 별개
}
```

**이유:** 상담원 이관 요청은 정보 수집 단계와 별개이므로 초기화 필요

---

## 🔄 전체 워크플로우 플로우

### 일반 대화 플로우

```
사용자 입력
  ↓
triage_agent
  ├─ intent_classification_tool 호출
  ├─ rag_search_tool 호출
  └─ LLM 판단 → triage_decision 결정
  ↓
answer_agent
  ├─ AUTO_HANDLE_OK → 답변 생성
  ├─ NEED_MORE_INFO → 질문 생성
  └─ HUMAN_REQUIRED → 상담사 연결 안내
  ↓
chat_db_storage → END
```

### 정보 수집 단계 플로우

```
턴 1: HUMAN_REQUIRED
  → AI: "상담사 연결하시겠습니까?"
  → 사용자: "예"
  ↓
턴 2: 정보 수집 시작
  → AI: "추가적인 질문을 드리겠습니다."
  → is_collecting_info = True, count = 0
  ↓
턴 3~7: 정보 수집 질문 (5회)
  → triage_agent: Tool 사용 안 하고 NEED_MORE_INFO 반환
  → answer_agent: 질문 생성, count 증가 (1 → 2 → 3 → 4 → 5)
  → chat_db_storage → END
  ↓
턴 8: 6번째 턴
  → answer_agent: "상담사 연결 예정입니다. 잠시만 기다려주세요."
  → count = 6
  → summary_agent → human_transfer → chat_db_storage → END
```

---

## 🐛 버그 수정

### 1. workflow.py 주석 오류
- **문제:** "5회 도달 시"라고 되어 있었으나 실제로는 6회
- **수정:** "6회 도달 시"로 변경

### 2. process_handover 정보 수집 상태 누락
- **문제:** 상담원 이관 요청 시 정보 수집 상태 초기화 없음
- **수정:** `is_collecting_info = False`, `info_collection_count = 0` 추가

### 3. suggested_action 덮어쓰기 문제
- **문제:** `human_transfer` 노드에서 설정한 `HANDOVER`가 `state_to_chat_response`에서 덮어씌워짐
- **수정:** `state`에 이미 설정된 `suggested_action` 우선 사용

---

## 📊 성능 및 개선 효과

### 1. 판단 정확도 향상
- **이전:** 유사도 점수와 키워드 기반 규칙
- **변경 후:** LLM이 문서 전체 내용을 분석하여 맥락적 판단
- **효과:** 더 정확한 triage 결정

### 2. 코드 유지보수성 향상
- 프롬프트 헬퍼 함수 분리
- 명확한 분기 처리
- 주석 및 문서화 개선

### 3. 확장성 향상
- Triage Decision Type Enum으로 타입 안정성 확보
- 정보 수집 단계 상태 관리 체계화

---

## ⚠️ 주의사항

### 1. 정보 수집 상태 관리 (Option B)
- 현재는 `conversation_history` 분석으로 상태 복원
- 향후 DB 스키마에 `is_collecting_info`, `info_collection_count` 필드 추가 고려 (Option A)
- 마이그레이션 가이드: `docs/MIGRATION_GUIDE_INFO_COLLECTION.md` 참고

### 2. 에러 처리
- `answer_agent`에서 질문 생성 실패 시 `info_collection_count` 증가 안 함 (의도된 동작)
- 에러 발생 시에도 상태는 유지됨

### 3. LLM 의존성
- `triage_agent`의 판단이 LLM에 의존하므로 LLM 응답 품질이 중요
- 프롬프트 튜닝이 필요할 수 있음

---

## 🧪 테스트 시나리오

### 시나리오 1: 일반 답변 생성
1. 사용자: "카드론 한도가 얼마야?"
2. triage_agent: AUTO_HANDLE_OK
3. answer_agent: RAG 문서 기반 답변 생성

### 시나리오 2: 추가 정보 요청
1. 사용자: "대출"
2. triage_agent: NEED_MORE_INFO
3. answer_agent: "어떤 종류의 대출을 원하시나요?" 질문 생성

### 시나리오 3: 상담사 연결 (정보 수집 포함)
1. 사용자: "복잡한 업무"
2. triage_agent: HUMAN_REQUIRED
3. answer_agent: "상담사 연결하시겠습니까?"
4. 사용자: "예"
5. answer_agent: "추가적인 질문을 드리겠습니다."
6. 5회 질문 진행
7. 6번째 턴: "상담사 연결 예정입니다"
8. summary_agent → human_transfer

---

## 📚 참고 문서

- 마이그레이션 가이드: `docs/MIGRATION_GUIDE_INFO_COLLECTION.md`
- 상태 정의: `ai_engine/graph/state.py` (상단 주석)

---

## ✅ 체크리스트

- [x] TriageDecisionType Enum 추가
- [x] 노드명 변경 (decision_agent → triage_agent)
- [x] triage_agent_node LLM 기반 판단 로직 구현
- [x] answer_agent_node 분기 처리 구현
- [x] 정보 수집 단계 구현 (5회 질문 + 6번째 연결 안내)
- [x] workflow 라우팅 로직 수정
- [x] 상태 복원 로직 구현
- [x] suggested_action 우선순위 수정
- [x] 주석 및 문서화 개선
- [x] 버그 수정 (주석 오류, 상태 초기화 등)

---

**작성일:** 2025년
**검토 필요:** 팀 리뷰

