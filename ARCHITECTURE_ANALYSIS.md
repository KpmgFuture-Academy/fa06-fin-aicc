# 프로젝트 아키텍처 및 파일 연결 분석

## 📋 목차
1. [전체 구조 개요](#전체-구조-개요)
2. [데이터 흐름](#데이터-흐름)
3. [모듈별 상세 분석](#모듈별-상세-분석)
4. [의존성 그래프](#의존성-그래프)

---

## 전체 구조 개요

### 프로젝트 계층 구조
```
fa06-fin-aicc/
├── frontend/              # React + TypeScript 프론트엔드
├── app/                   # FastAPI 백엔드
│   ├── api/v1/           # API 엔드포인트
│   ├── core/             # 설정 및 데이터베이스
│   ├── models/           # SQLAlchemy 모델
│   ├── schemas/          # Pydantic 스키마
│   └── services/         # 비즈니스 로직
├── ai_engine/            # AI 엔진 (LangGraph 워크플로우)
│   ├── graph/            # LangGraph 워크플로우
│   │   ├── nodes/        # 워크플로우 노드들
│   │   ├── tools/        # LangChain Tools
│   │   ├── state.py      # 상태 정의
│   │   └── workflow.py   # 워크플로우 정의
│   ├── ingestion/        # 문서 수집 및 파싱
│   ├── prompts/          # 프롬프트 템플릿
│   ├── utils/            # 유틸리티 함수
│   └── vector_store.py   # 벡터 DB 관리
├── data/                 # KB 문서 데이터
├── scripts/              # 스크립트
└── chroma_db/            # ChromaDB 저장소
```

---

## 데이터 흐름

### 1. 사용자 메시지 처리 흐름

```
Frontend (React)
    │
    ├─> api.ts: chatApi.sendMessage()
    │
    ▼
Backend API (FastAPI)
    │
    ├─> app/main.py
    │   └─> app.include_router(chat.router)
    │
    ├─> app/api/v1/chat.py
    │   └─> @router.post("/message")
    │       └─> process_chat_message(request)
    │
    ▼
Workflow Service
    │
    ├─> app/services/workflow_service.py
    │   ├─> chat_request_to_state()      # ChatRequest → GraphState 변환
    │   └─> get_workflow().ainvoke()     # LangGraph 워크플로우 실행
    │
    ▼
LangGraph Workflow
    │
    ├─> ai_engine/graph/workflow.py
    │   └─> build_workflow()
    │       └─> StateGraph(GraphState)
    │
    ├─> Entry Point: triage_agent
    │
    ▼
[워크플로우 노드 실행 순서]
    │
    1. triage_agent_node
    │   ├─> intent_classification_tool    # 의도 분류
    │   ├─> rag_search_tool               # 문서 검색
    │   └─> LLM 판단 (AUTO_HANDLE_OK/NEED_MORE_INFO/HUMAN_REQUIRED)
    │
    2. answer_agent_node
    │   └─> triage_decision에 따라 답변 생성
    │       ├─> AUTO_HANDLE_OK: RAG 기반 답변
    │       ├─> NEED_MORE_INFO: 추가 질문 생성
    │       └─> HUMAN_REQUIRED: 상담사 연결 안내
    │
    3. (조건부) summary_agent_node
    │   └─> 정보 수집 6회 완료 시 대화 요약
    │
    4. (조건부) human_transfer_node
    │   └─> 상담사 이관 정보 생성
    │
    5. chat_db_storage_node
    │   └─> DB에 대화 저장
    │
    ▼
GraphState → ChatResponse 변환
    │
    ├─> app/services/workflow_service.py
    │   └─> state_to_chat_response()
    │
    ▼
Frontend에 응답 반환
    │
    └─> app/api/v1/chat.py
        └─> return ChatResponse(...)
```

---

## 모듈별 상세 분석

### 🔵 Frontend 계층

#### 파일 구조 및 연결
```
frontend/
├── src/
│   ├── main.tsx                 # 진입점
│   ├── App.tsx                  # 메인 컴포넌트
│   ├── components/
│   │   ├── ChatWindow.tsx       # 채팅 UI
│   │   ├── ChatInput.tsx        # 입력 컴포넌트
│   │   └── HandoverModal.tsx    # 상담사 이관 모달
│   ├── services/
│   │   └── api.ts               # 백엔드 API 클라이언트
│   └── types/
│       └── api.ts               # TypeScript 타입 정의
```

**주요 연결 관계:**
- `main.tsx` → `App.tsx` 렌더링
- `App.tsx` → `ChatWindow.tsx`, `HandoverModal.tsx` 사용
- `ChatWindow.tsx` → `api.ts`의 `chatApi.sendMessage()` 호출
- `api.ts` → `http://localhost:8000/api/v1/chat/message` POST 요청

### 🟢 Backend API 계층

#### 1. 진입점: `app/main.py`
```python
# 주요 역할:
- FastAPI 앱 초기화
- CORS 설정
- 라우터 등록
- Startup/Shutdown 이벤트 처리
- DB 초기화
- 벡터 DB 초기화 확인
```

**연결 관계:**
- `app/main.py` → `app/core/config.py` (settings)
- `app/main.py` → `app/core/database.py` (init_db, engine)
- `app/main.py` → `app/api/v1/chat.py` (router 등록)
- `app/main.py` → `app/api/v1/handover.py` (router 등록)

#### 2. API 라우터: `app/api/v1/chat.py`
```python
# 주요 역할:
- POST /api/v1/chat/message 엔드포인트
- 입력 검증
- workflow_service.process_chat_message() 호출
```

**연결 관계:**
- `chat.py` → `app/services/workflow_service.py` (process_chat_message)
- `chat.py` → `app/schemas/chat.py` (ChatRequest, ChatResponse)

#### 3. 설정: `app/core/config.py`
```python
# 주요 역할:
- .env 파일에서 설정 로드
- 데이터베이스 URL
- OpenAI/LM Studio 설정
- 벡터 DB 설정
- Hybrid Search 설정
```

**연결 관계:**
- 모든 모듈이 `settings` 사용
- `app/core/config.py` → `.env` 파일 읽기

#### 4. 데이터베이스: `app/core/database.py`
```python
# 주요 역할:
- SQLAlchemy 엔진 생성
- 세션 팩토리 생성
- Base 클래스 정의
```

**연결 관계:**
- `database.py` → `app/core/config.py` (database_url)
- `app/models/chat_message.py` → `database.py` (Base 상속)
- `app/services/session_manager.py` → `database.py` (SessionLocal)

### 🟡 AI Engine 계층

#### 1. 워크플로우 정의: `ai_engine/graph/workflow.py`
```python
# 주요 역할:
- LangGraph StateGraph 생성
- 노드 등록 및 엣지 연결
- 조건부 분기 로직
```

**연결 관계:**
- `workflow.py` → `ai_engine/graph/state.py` (GraphState)
- `workflow.py` → `ai_engine/graph/nodes/triage_agent.py`
- `workflow.py` → `ai_engine/graph/nodes/answer_agent.py`
- `workflow.py` → `ai_engine/graph/nodes/chat_db_storage.py`
- `workflow.py` → `ai_engine/graph/nodes/summary_agent.py`
- `workflow.py` → `ai_engine/graph/nodes/human_transfer.py`

#### 2. 상태 정의: `ai_engine/graph/state.py`
```python
# 주요 역할:
- GraphState TypedDict 정의
- RetrievedDocument 정의
- ConversationMessage 정의
```

**연결 관계:**
- 모든 노드와 서비스가 `GraphState` 사용
- `state.py` → `app/schemas/` (타입 참조)

#### 3. Triage Agent 노드: `ai_engine/graph/nodes/triage_agent.py`
```python
# 주요 역할:
- 사용자 메시지 분석
- 의도 분류 Tool 호출
- RAG 검색 Tool 호출
- 처리 방식 결정 (AUTO_HANDLE_OK/NEED_MORE_INFO/HUMAN_REQUIRED)
```

**연결 관계:**
- `triage_agent.py` → `ai_engine/graph/tools/intent_classification_tool.py`
- `triage_agent.py` → `ai_engine/graph/tools/rag_search_tool.py`
- `triage_agent.py` → `ai_engine/graph/tools/chat_history_tool.py`
- `triage_agent.py` → `app/core/config.py` (LLM 설정)
- `triage_agent.py` → `langchain_openai.ChatOpenAI`

#### 4. Answer Agent 노드: `ai_engine/graph/nodes/answer_agent.py`
```python
# 주요 역할:
- triage_decision에 따라 답변 생성
- AUTO_HANDLE_OK: RAG 문서 기반 답변
- NEED_MORE_INFO: 추가 질문 생성
- HUMAN_REQUIRED: 상담사 연결 안내
```

**연결 관계:**
- `answer_agent.py` → `ai_engine/prompts/templates.py` (SYSTEM_PROMPT)
- `answer_agent.py` → `app/core/config.py` (LLM 설정)
- `answer_agent.py` → `langchain_openai.ChatOpenAI`

#### 5. Tools: `ai_engine/graph/tools/`

##### 5.1 Intent Classification Tool
```
ai_engine/graph/tools/intent_classification_tool.py
    │
    └─> Hana Card 모델 사용
        └─> ai_engine/ingestion/bert_financial_intent_classifier/scripts/inference.py
```

**연결 관계:**
- `intent_classification_tool.py` → `models/hana_card_model/` (모델 로드)
- `intent_classification_tool.py` → `data/kb_finance_insurance_60items_v1.json` (키워드)

##### 5.2 RAG Search Tool
```
ai_engine/graph/tools/rag_search_tool.py
    │
    └─> ai_engine/vector_store.py
        └─> search_documents()
            ├─> ChromaDB 벡터 검색
            ├─> BM25 검색 (Hybrid Search)
            └─> Reranking (선택적)
```

**연결 관계:**
- `rag_search_tool.py` → `ai_engine/vector_store.py` (search_documents)
- `vector_store.py` → `app/core/config.py` (벡터 DB 설정)
- `vector_store.py` → `chroma_db/` (ChromaDB 저장소)
- `vector_store.py` → `langchain_huggingface.HuggingFaceEmbeddings` (임베딩)

##### 5.3 Chat History Tool
```
ai_engine/graph/tools/chat_history_tool.py
    │
    └─> 대화 이력 포맷팅
```

**연결 관계:**
- `chat_history_tool.py` → `ai_engine/graph/state.py` (ConversationMessage)

#### 6. 벡터 스토어: `ai_engine/vector_store.py`
```python
# 주요 역할:
- ChromaDB 초기화
- 문서 추가 (add_documents)
- 문서 검색 (search_documents)
- Hybrid Search (벡터 + BM25)
- Reranking
```

**연결 관계:**
- `vector_store.py` → `chromadb.PersistentClient`
- `vector_store.py` → `langchain_huggingface.HuggingFaceEmbeddings`
- `vector_store.py` → `langchain_chroma.Chroma`
- `vector_store.py` → `langchain_community.retrievers.BM25Retriever`
- `vector_store.py` → `sentence_transformers.CrossEncoder` (Reranking)

#### 7. 문서 수집: `ai_engine/ingestion/`

```
ai_engine/ingestion/
├── loader.py              # JSON 파일 로드
├── parser.py              # 문서 파싱
└── bert_financial_intent_classifier/
    └── scripts/
        └── inference.py   # 의도 분류 모델
```

**연결 관계:**
- `loader.py` → `data/kb_finance_insurance_60items_v1.json`
- `parser.py` → `loader.py` (JSON 파싱)
- `scripts/ingest_kb_documents.py` → `loader.py`, `parser.py`, `vector_store.py`

### 🔴 Service 계층

#### 1. Workflow Service: `app/services/workflow_service.py`
```python
# 주요 역할:
- ChatRequest → GraphState 변환
- GraphState → ChatResponse 변환
- 워크플로우 실행
```

**연결 관계:**
- `workflow_service.py` → `ai_engine/graph/workflow.py` (build_workflow)
- `workflow_service.py` → `app/services/session_manager.py` (대화 이력 로드)
- `workflow_service.py` → `app/schemas/` (타입 변환)

#### 2. Session Manager: `app/services/session_manager.py`
```python
# 주요 역할:
- 세션별 대화 이력 관리
- DB에서 대화 이력 조회
```

**연결 관계:**
- `session_manager.py` → `app/core/database.py` (SessionLocal)
- `session_manager.py` → `app/models/chat_message.py` (ChatSession, ChatMessage)

### 🟣 Database 계층

#### 모델: `app/models/chat_message.py`
```python
# 주요 역할:
- ChatSession 테이블 정의
- ChatMessage 테이블 정의
```

**연결 관계:**
- `chat_message.py` → `app/core/database.py` (Base)
- `chat_db_storage.py` → `chat_message.py` (DB 저장)

---

## 의존성 그래프

### 전체 의존성 흐름

```
Frontend (React)
    │
    └─ HTTP ─> Backend (FastAPI)
                    │
                    ├─> API Layer (app/api/v1/)
                    │       │
                    │       └─> Service Layer (app/services/)
                    │               │
                    │               └─> AI Engine (ai_engine/)
                    │                       │
                    │                       ├─> LangGraph Workflow
                    │                       │       │
                    │                       │       ├─> Nodes
                    │                       │       │   ├─> triage_agent
                    │                       │       │   ├─> answer_agent
                    │                       │       │   ├─> summary_agent
                    │                       │       │   ├─> human_transfer
                    │                       │       │   └─> chat_db_storage
                    │                       │       │
                    │                       │       └─> Tools
                    │                       │           ├─> intent_classification_tool
                    │                       │           ├─> rag_search_tool
                    │                       │           └─> chat_history_tool
                    │                       │
                    │                       ├─> Vector Store (ChromaDB)
                    │                       │       │
                    │                       │       ├─> Embeddings (HuggingFace)
                    │                       │       ├─> Hybrid Search (BM25)
                    │                       │       └─> Reranking (Cross-Encoder)
                    │                       │
                    │                       └─> Intent Classifier (Hana Card)
                    │
                    └─> Database Layer (SQLAlchemy)
                            │
                            └─> MySQL/MariaDB
```

### 핵심 의존성 체인

#### 1. API 요청 → 응답 체인
```
Frontend api.ts
    ↓
app/api/v1/chat.py (router)
    ↓
app/services/workflow_service.py (process_chat_message)
    ↓
ai_engine/graph/workflow.py (build_workflow)
    ↓
LangGraph 실행 (노드들 순차 실행)
    ↓
GraphState → ChatResponse 변환
    ↓
Frontend에 응답 반환
```

#### 2. 의도 분류 체인
```
triage_agent_node
    ↓
intent_classification_tool
    ↓
bert_intent_classifier/inference.py
    ↓
Hana Card 모델 (models/hana_card_model/)
    ↓
의도 분류 결과 반환
```

#### 3. RAG 검색 체인
```
triage_agent_node
    ↓
rag_search_tool
    ↓
vector_store.search_documents()
    ↓
┌─────────────────────────┐
│ 1. 벡터 검색 (ChromaDB)  │
│ 2. BM25 검색 (Hybrid)   │
│ 3. Reranking (선택적)   │
└─────────────────────────┘
    ↓
검색 결과 반환
```

#### 4. 데이터베이스 저장 체인
```
answer_agent_node
    ↓
chat_db_storage_node
    ↓
app/models/chat_message.py (ChatSession, ChatMessage)
    ↓
app/core/database.py (SessionLocal)
    ↓
MySQL/MariaDB
```

#### 5. 벡터 DB 문서 수집 체인
```
scripts/ingest_kb_documents.py
    ↓
ai_engine/ingestion/loader.py (JSON 로드)
    ↓
ai_engine/ingestion/parser.py (문서 파싱)
    ↓
ai_engine/vector_store.py (add_documents)
    ↓
ChromaDB (chroma_db/)
```

---

## 주요 설정 파일

### 1. `.env` 파일
```env
# 데이터베이스
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aicc_db

# LLM 설정
OPENAI_API_KEY=sk-...
USE_LM_STUDIO=false
LM_STUDIO_BASE_URL=http://localhost:1234/v1

# 벡터 DB
VECTOR_DB_PATH=./chroma_db
EMBEDDING_MODEL=jhgan/ko-sroberta-multitask
COLLECTION_NAME=financial_documents

# Hybrid Search
ENABLE_HYBRID_SEARCH=true
BM25_KOREAN_TOKENIZER=kiwi

# Reranking
ENABLE_RERANKING=true
RERANKER_MODEL=Dongjin-kr/ko-reranker
```

### 2. `requirements.txt`
```
fastapi
langchain
langgraph
chromadb
sentence-transformers
transformers
torch
sqlalchemy
pymysql
...
```

---

## 데이터 흐름 예시

### 시나리오 1: 일반 질문 처리
```
1. 사용자: "대출 금리가 궁금해요"
   ↓
2. Frontend → Backend API
   ↓
3. workflow_service.process_chat_message()
   ↓
4. triage_agent_node:
   - intent_classification_tool → "대출" 의도
   - rag_search_tool → 관련 문서 검색
   - LLM 판단 → AUTO_HANDLE_OK
   ↓
5. answer_agent_node:
   - RAG 문서 기반 답변 생성
   ↓
6. chat_db_storage_node:
   - DB에 대화 저장
   ↓
7. ChatResponse 반환
```

### 시나리오 2: 상담사 이관
```
1. 사용자: "상담사 연결해주세요"
   ↓
2. triage_agent_node:
   - 직접 상담원 연결 요청 감지
   - HUMAN_REQUIRED 반환
   ↓
3. answer_agent_node:
   - "상담사 연결하시겠습니까?" 메시지
   ↓
4. 사용자: "예"
   ↓
5. answer_agent_node:
   - is_collecting_info = True 설정
   - 정보 수집 시작
   ↓
6. 정보 수집 질문 5회 진행
   ↓
7. 6번째 턴:
   - summary_agent_node → 대화 요약
   - human_transfer_node → 이관 정보 생성
   - chat_db_storage_node → DB 저장
   ↓
8. HandoverResponse 반환
```

---

## 요약

### 핵심 아키텍처 패턴
1. **계층형 아키텍처**: Frontend → API → Service → AI Engine → Database
2. **LangGraph 기반 워크플로우**: 상태 기반 그래프 실행
3. **Tool 패턴**: LangChain Tools로 기능 분리
4. **Hybrid Search**: 벡터 검색 + BM25 검색 결합
5. **Reranking**: Cross-Encoder로 검색 결과 재정렬

### 주요 기술 스택
- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI + Python
- **AI Framework**: LangChain + LangGraph
- **Vector DB**: ChromaDB
- **Database**: MySQL/MariaDB (SQLAlchemy)
- **Embedding**: HuggingFace (ko-sroberta-multitask)
- **LLM**: OpenAI GPT-4o-mini 또는 LM Studio

### 데이터 흐름 특징
- **Stateless API**: 각 요청마다 독립적으로 처리
- **상태 관리**: GraphState를 통해 워크플로우 상태 전달
- **세션 관리**: DB를 통해 대화 이력 유지
- **비동기 처리**: FastAPI async/await 활용

