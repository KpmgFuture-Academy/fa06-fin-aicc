# chat_history_tool 연결 관계 분석

## 📋 목차
1. [개요](#개요)
2. [파일 구조 및 정의](#파일-구조-및-정의)
3. [연결된 파일들](#연결된-파일들)
4. [데이터 흐름](#데이터-흐름)
5. [변수 및 타입 연결](#변수-및-타입-연결)
6. [사용 시나리오](#사용-시나리오)

---

## 개요

`chat_history_tool`은 대화 이력(`conversation_history`)을 LLM이 읽기 쉬운 형식으로 포맷팅하는 LangChain Tool입니다. 주로 `triage_agent_node`에서 사용되어 이전 대화 맥락을 LLM에 제공합니다.

---

## 파일 구조 및 정의

### 1. 정의 파일
**`ai_engine/graph/tools/chat_history_tool.py`**

```python
# 주요 함수들:
1. format_chat_history() - 메인 Tool 함수
2. get_recent_user_messages() - 최근 사용자 메시지만 추출
3. summarize_conversation_context() - 대화 맥락 요약

# Tool 인스턴스:
chat_history_tool = format_chat_history
```

### 2. Export 파일
**`ai_engine/graph/tools/__init__.py`**

```python
from ai_engine.graph.tools.chat_history_tool import chat_history_tool

__all__ = [
    "chat_history_tool",
    ...
]
```

---

## 연결된 파일들

### 직접 연결 (Import/Export 관계)

```
ai_engine/graph/tools/chat_history_tool.py
    │
    ├─> Import:
    │   ├─> from langchain_core.tools import tool          # LangChain Tool 데코레이터
    │   └─> from ai_engine.graph.state import ConversationMessage  # 타입 정의
    │
    └─> Export:
        └─> chat_history_tool (format_chat_history 함수)
            │
            ▼
ai_engine/graph/tools/__init__.py
    │
    ├─> from ai_engine.graph.tools.chat_history_tool import chat_history_tool
    │
    └─> __all__에 포함
        │
        ▼
ai_engine/graph/nodes/triage_agent.py
    │
    └─> from ai_engine.graph.tools import chat_history_tool
```

### 간접 연결 (데이터 흐름)

```
1. 데이터 소스:
   app/services/session_manager.py
       └─> get_conversation_history()
           └─> DB에서 ConversationMessage 리스트 생성
   
2. 데이터 전달:
   app/services/workflow_service.py
       └─> chat_request_to_state()
           └─> GraphState에 conversation_history 포함
   
3. Tool 호출:
   ai_engine/graph/nodes/triage_agent.py
       └─> chat_history_tool.invoke()
   
4. 데이터 저장:
   ai_engine/graph/nodes/chat_db_storage.py
       └─> DB 저장 후 conversation_history 업데이트
```

---

## 데이터 흐름

### 전체 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│ 1. DB에서 대화 이력 로드                                      │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ app/services/session_manager.py                              │
│                                                              │
│ session_manager.get_conversation_history(session_id)        │
│   ├─> DB 쿼리 (ChatSession, ChatMessage)                    │
│   └─> List[ConversationMessage] 반환                        │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ app/services/workflow_service.py                            │
│                                                              │
│ chat_request_to_state(request: ChatRequest)                 │
│   ├─> conversation_history = session_manager.get_...()      │
│   └─> GraphState 생성                                        │
│       └─> state["conversation_history"] = conversation_history│
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ LangGraph Workflow 실행                                      │
│   └─> workflow.ainvoke(initial_state)                       │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ ai_engine/graph/nodes/triage_agent.py                       │
│                                                              │
│ triage_agent_node(state: GraphState)                        │
│   ├─> conversation_history = state.get("conversation_history")│
│   │                                                          │
│   ├─> if conversation_history:                              │
│   │   └─> formatted_history = chat_history_tool.invoke({    │
│   │           "conversation_history": conversation_history, │
│   │           "max_messages": 10,                           │
│   │           "include_timestamps": False                   │
│   │       })                                                │
│   │                                                          │
│   └─> formatted_history를 프롬프트에 포함                    │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ ai_engine/graph/tools/chat_history_tool.py                  │
│                                                              │
│ format_chat_history(                                        │
│     conversation_history: List[ConversationMessage],        │
│     max_messages: int = 10,                                 │
│     include_timestamps: bool = False                        │
│ ) -> str                                                    │
│                                                              │
│ 반환 형식:                                                   │
│ "[대화 이력]                                                │
│  사용자: 메시지1                                            │
│  어시스턴트: 응답1                                          │
│  ..."                                                       │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM 프롬프트에 포함                                          │
│                                                              │
│ system_message + human_message                              │
│   └─> formatted_history 포함                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 변수 및 타입 연결

### 1. 핵심 타입: `ConversationMessage`

**정의 위치**: `ai_engine/graph/state.py`

```python
class ConversationMessage(TypedDict):
    """대화 메시지 단위"""
    role: str          # "user" 또는 "assistant"
    message: str       # 메시지 내용
    timestamp: Optional[str]  # 타임스탬프 (ISO 형식)
```

**사용하는 파일들**:
- `ai_engine/graph/state.py` - 타입 정의
- `ai_engine/graph/tools/chat_history_tool.py` - 함수 파라미터 타입
- `app/services/session_manager.py` - 반환 타입
- `app/services/workflow_service.py` - 함수 파라미터 타입
- `ai_engine/graph/nodes/chat_db_storage.py` - 생성 및 사용
- `ai_engine/graph/nodes/triage_agent.py` - 사용

### 2. GraphState의 conversation_history 필드

**정의 위치**: `ai_engine/graph/state.py`

```python
class GraphState(TypedDict, total=False):
    conversation_history: List[ConversationMessage]  # 전체 대화 이력
    ...
```

**데이터 흐름**:
```
1. session_manager.get_conversation_history()
   └─> List[ConversationMessage] 생성
       │
2. workflow_service.chat_request_to_state()
   └─> state["conversation_history"] = conversation_history
       │
3. triage_agent_node()
   └─> conversation_history = state.get("conversation_history", [])
       └─> chat_history_tool.invoke({"conversation_history": conversation_history, ...})
           │
4. chat_db_storage_node()
   └─> DB 저장 후 state["conversation_history"] 업데이트
```

### 3. chat_history_tool 함수 시그니처

**정의 위치**: `ai_engine/graph/tools/chat_history_tool.py`

```python
@tool
def format_chat_history(
    conversation_history: List[ConversationMessage],  # 입력: 대화 이력 리스트
    max_messages: int = 10,                          # 최대 메시지 수 (기본값: 10)
    include_timestamps: bool = False                 # 타임스탬프 포함 여부
) -> str:                                            # 출력: 포맷팅된 문자열
```

**호출 방식**:
```python
# triage_agent.py에서 호출
formatted_history = chat_history_tool.invoke({
    "conversation_history": conversation_history,  # List[ConversationMessage]
    "max_messages": 10,                            # int
    "include_timestamps": False                    # bool
})
# 반환: str (포맷팅된 대화 이력 문자열)
```

### 4. 데이터 변환 체인

```
DB (MySQL/MariaDB)
    │
    ├─> ChatSession 테이블
    └─> ChatMessage 테이블
        │
        ▼
app/models/chat_message.py
    ├─> ChatSession (SQLAlchemy 모델)
    └─> ChatMessage (SQLAlchemy 모델)
        │
        ▼
app/services/session_manager.py
    └─> ChatMessage → ConversationMessage 변환
        │
        ▼
ai_engine/graph/state.py
    └─> ConversationMessage (TypedDict)
        │
        ▼
GraphState
    └─> conversation_history: List[ConversationMessage]
        │
        ▼
ai_engine/graph/tools/chat_history_tool.py
    └─> format_chat_history(conversation_history) → str
        │
        ▼
LLM 프롬프트
    └─> 포맷팅된 문자열 포함
```

---

## 변수 연결 상세

### 1. session_manager 변수

**위치**: `app/services/session_manager.py`

```python
# 전역 인스턴스
session_manager = SessionManager()
```

**연결 관계**:
- `workflow_service.py`에서 import하여 사용
  ```python
  from app.services.session_manager import session_manager
  
  conversation_history = session_manager.get_conversation_history(request.session_id)
  ```

### 2. conversation_history 변수 (GraphState 내)

**생성 위치**:
1. `workflow_service.py` - `chat_request_to_state()` 함수
   ```python
   conversation_history = session_manager.get_conversation_history(request.session_id)
   state["conversation_history"] = conversation_history
   ```

2. `chat_db_storage.py` - DB 저장 후 업데이트
   ```python
   # DB에서 최신 대화 이력 로드
   messages = db.query(ChatMessage).filter(...).all()
   conversation_history: list[ConversationMessage] = []
   for msg in messages:
       conversation_history.append(ConversationMessage(...))
   state["conversation_history"] = conversation_history
   ```

**사용 위치**:
- `triage_agent.py` - Tool 호출 전에 가져옴
  ```python
  conversation_history = state.get("conversation_history", [])
  ```

### 3. formatted_history 변수

**위치**: `ai_engine/graph/nodes/triage_agent.py`

```python
formatted_history = chat_history_tool.invoke({
    "conversation_history": conversation_history,
    "max_messages": 10,
    "include_timestamps": False
})
```

**사용**: LLM 프롬프트에 포함
```python
history_info = f"\n\n{formatted_history}"
human_message = HumanMessage(content=f"""
...
{history_info}
...
""")
```

---

## 사용 시나리오

### 시나리오 1: 첫 대화 (대화 이력 없음)

```
1. session_manager.get_conversation_history(session_id)
   └─> [] (빈 리스트 반환)

2. workflow_service.chat_request_to_state()
   └─> state["conversation_history"] = []

3. triage_agent_node()
   ├─> conversation_history = state.get("conversation_history", [])
   ├─> if conversation_history:  # False
   │   └─> 건너뜀
   └─> formatted_history = "대화 이력이 없습니다. (첫 대화입니다)"

4. LLM 프롬프트에 포함
   └─> "대화 이력이 없습니다. (첫 대화입니다)"
```

### 시나리오 2: 이전 대화가 있는 경우

```
1. session_manager.get_conversation_history(session_id)
   └─> [
        ConversationMessage(role="user", message="대출 금리가 궁금해요", ...),
        ConversationMessage(role="assistant", message="...", ...),
        ConversationMessage(role="user", message="이자율은?", ...),
        ...
       ]

2. workflow_service.chat_request_to_state()
   └─> state["conversation_history"] = [위 리스트]

3. triage_agent_node()
   ├─> conversation_history = state.get("conversation_history", [])
   ├─> if conversation_history:  # True
   │   └─> formatted_history = chat_history_tool.invoke({
   │           "conversation_history": conversation_history,
   │           "max_messages": 10,
   │           "include_timestamps": False
   │       })
   │
   └─> formatted_history =
       "[대화 이력]
        사용자: 대출 금리가 궁금해요
        어시스턴트: ...
        사용자: 이자율은?
        ..."

4. LLM 프롬프트에 포함
   └─> formatted_history가 프롬프트에 추가되어
       이전 대화 맥락을 참고하여 판단 가능
```

### 시나리오 3: 대화 이력이 10개 초과인 경우

```
1. conversation_history에 15개 메시지 존재

2. chat_history_tool.invoke({
       "conversation_history": conversation_history,  # 15개
       "max_messages": 10,
       ...
   })

3. format_chat_history() 내부:
   ├─> recent_messages = conversation_history[-10:]  # 최근 10개만
   └─> result = "...(최근 10개 메시지)...\n(총 15개 메시지 중 최근 10개만 표시)"

4. formatted_history에 최근 10개만 포함됨 (토큰 제한 고려)
```

---

## 의존성 그래프

```
chat_history_tool
    │
    ├─> 의존성 (Import):
    │   ├─> langchain_core.tools.tool (데코레이터)
    │   └─> ai_engine.graph.state.ConversationMessage (타입)
    │
    ├─> 사용되는 곳 (호출):
    │   └─> ai_engine.graph.nodes.triage_agent.triage_agent_node()
    │
    └─> 데이터 소스 (간접):
        ├─> app.services.session_manager.SessionManager
        │   └─> get_conversation_history()
        │       └─> DB (ChatSession, ChatMessage)
        │
        └─> app.services.workflow_service
            └─> chat_request_to_state()
                └─> session_manager.get_conversation_history()
```

---

## 핵심 연결 요약

### 파일 연결
1. **정의**: `ai_engine/graph/tools/chat_history_tool.py`
2. **Export**: `ai_engine/graph/tools/__init__.py`
3. **사용**: `ai_engine/graph/nodes/triage_agent.py`
4. **타입 정의**: `ai_engine/graph/state.py`

### 변수 연결
1. **`conversation_history`**: `List[ConversationMessage]`
   - 생성: `session_manager.get_conversation_history()`
   - 저장: `GraphState["conversation_history"]`
   - 사용: `chat_history_tool.invoke()`의 입력

2. **`formatted_history`**: `str`
   - 생성: `chat_history_tool.invoke()`의 출력
   - 사용: LLM 프롬프트에 포함

### 데이터 흐름
```
DB → SessionManager → WorkflowService → GraphState 
    → TriageAgent → chat_history_tool → LLM 프롬프트
```

---

## 추가 정보

### Tool 내부 함수들

1. **`format_chat_history`** (메인 Tool)
   - 대화 이력을 포맷팅
   - 최근 N개만 선택 가능
   - 타임스탬프 포함/제외 옵션

2. **`get_recent_user_messages`** (미사용)
   - 최근 사용자 메시지만 추출
   - 현재 코드에서는 사용되지 않음

3. **`summarize_conversation_context`** (미사용)
   - 대화 맥락 요약
   - 현재 코드에서는 사용되지 않음

### 주의사항

1. **조건부 호출**: `triage_agent.py`에서 대화 이력이 있을 때만 호출
   ```python
   if conversation_history:
       formatted_history = chat_history_tool.invoke({...})
   else:
       formatted_history = "대화 이력이 없습니다. (첫 대화입니다)"
   ```

2. **토큰 제한**: `max_messages=10`으로 제한하여 최근 10개만 포함
   - LLM 프롬프트 토큰 제한 고려
   - 긴 대화 이력의 경우 일부만 포함

3. **타임스탬프 제외**: `include_timestamps=False`
   - 현재는 타임스탬프를 프롬프트에 포함하지 않음
   - 필요시 True로 변경 가능



