# 파일 연결 관계도

## 🔗 주요 파일 연결 맵

### 1. API 요청 처리 흐름

```
frontend/src/services/api.ts
    └─> POST /api/v1/chat/message
            │
            ▼
app/main.py
    ├─> app.include_router(chat.router)
    └─> app.include_router(handover.router)
            │
            ▼
app/api/v1/chat.py
    └─> @router.post("/message")
            └─> process_chat_message(request)
                    │
                    ▼
app/services/workflow_service.py
    ├─> chat_request_to_state()         # ChatRequest → GraphState
    ├─> get_workflow().ainvoke()        # 워크플로우 실행
    └─> state_to_chat_response()        # GraphState → ChatResponse
```

### 2. LangGraph 워크플로우 구조

```
ai_engine/graph/workflow.py
    ├─> build_workflow()
    │   └─> StateGraph(GraphState)
    │
    ├─> 노드 등록:
    │   ├─> "triage_agent"      → triage_agent_node
    │   ├─> "answer_agent"      → answer_agent_node
    │   ├─> "summary_agent"     → summary_agent_node
    │   ├─> "human_transfer"    → consultant_transfer_node
    │   └─> "chat_db_storage"   → chat_db_storage_node
    │
    └─> 엣지 연결:
        ├─> Entry Point: triage_agent
        ├─> triage_agent → answer_agent (항상)
        ├─> answer_agent → summary_agent (info_collection_count >= 6)
        ├─> answer_agent → chat_db_storage (일반 케이스)
        ├─> summary_agent → human_transfer
        ├─> human_transfer → chat_db_storage
        └─> chat_db_storage → END
```

### 3. Triage Agent 노드 상세 연결

```
ai_engine/graph/nodes/triage_agent.py
    │
    ├─> Tools 직접 호출:
    │   ├─> intent_classification_tool.invoke()
    │   │       │
    │   │       └─> ai_engine/graph/tools/intent_classification_tool.py
    │   │               │
    │   │               └─> Final Classifier 모델 (LoRA 기반 KcELECTRA, 38개 카테고리)
    │   │                   └─> ai_engine/ingestion/bert_financial_intent_classifier/scripts/inference.py
    │   │                       └─> models/final_classifier_model/model_final/ (모델 파일)
    │   │
    │   ├─> rag_search_tool.invoke()
    │   │       │
    │   │       └─> ai_engine/graph/tools/rag_search_tool.py
    │   │               │
    │   │               └─> ai_engine/vector_store.py
    │   │                       │
    │   │                       ├─> search_documents()
    │   │                       │   ├─> ChromaDB 벡터 검색
    │   │                       │   ├─> BM25 검색 (Hybrid Search)
    │   │                       │   └─> Reranking (Cross-Encoder)
    │   │                       │
    │   │                       └─> chroma_db/ (저장소)
    │   │
    │   └─> chat_history_tool.invoke()
    │           │
    │           └─> ai_engine/graph/tools/chat_history_tool.py
    │
    └─> LLM 판단 (ChatOpenAI)
            │
            └─> app/core/config.py
                    ├─> settings.use_lm_studio
                    └─> settings.openai_api_key
```

### 4. Answer Agent 노드 상세 연결

```
ai_engine/graph/nodes/answer_agent.py
    │
    ├─> triage_decision에 따라 분기:
    │
    ├─> AUTO_HANDLE_OK:
    │   ├─> _create_answer_generation_prompt()
    │   │       │
    │   │       └─> ai_engine/prompts/templates.py
    │   │               └─> SYSTEM_PROMPT
    │   │
    │   └─> LLM 답변 생성 (ChatOpenAI)
    │
    ├─> NEED_MORE_INFO:
    │   ├─> _create_question_generation_prompt()
    │   └─> LLM 질문 생성 (ChatOpenAI)
    │
    └─> HUMAN_REQUIRED:
        └─> 상담사 연결 안내 메시지
```

### 5. 데이터베이스 연결 체인

```
app/core/database.py
    ├─> engine (SQLAlchemy 엔진)
    ├─> SessionLocal (세션 팩토리)
    └─> Base (모델 베이스 클래스)
            │
            ▼
app/models/chat_message.py
    ├─> ChatSession (테이블 정의)
    │   └─> relationship("ChatMessage")
    │
    └─> ChatMessage (테이블 정의)
            │
            ├─> ForeignKey: ChatSession
            │
            ▼
사용하는 곳:
    ├─> ai_engine/graph/nodes/chat_db_storage.py
    │   └─> 대화 저장 (INSERT)
    │
    └─> app/services/session_manager.py
        └─> 대화 이력 조회 (SELECT)
```

### 6. 벡터 DB 연결 체인

```
scripts/ingest_kb_documents.py (문서 수집 스크립트)
    │
    ├─> ai_engine/ingestion/loader.py
    │   └─> load_kb_json()
    │       └─> data/kb_finance_insurance_60items_v1.json
    │
    ├─> ai_engine/ingestion/parser.py
    │   └─> parse_kb_document()
    │
    └─> ai_engine/vector_store.py
        ├─> add_documents()
        │   ├─> 텍스트 분할 (RecursiveCharacterTextSplitter)
        │   ├─> 임베딩 생성 (HuggingFaceEmbeddings)
        │   └─> ChromaDB에 저장
        │
        └─> chroma_db/ (저장소)
```

### 7. 벡터 검색 체인

```
ai_engine/vector_store.py
    │
    └─> search_documents(query)
        │
        ├─> 1단계: 메타 쿼리 필터링
        │
        ├─> 2단계: 쿼리 확장 (선택적)
        │   └─> ai_engine/utils/query_expansion.py
        │       └─> expand_query()
        │
        ├─> 3단계: Hybrid Search
        │   ├─> 벡터 검색 (ChromaDB)
        │   │   └─> get_embeddings()
        │   │       └─> HuggingFaceEmbeddings
        │   │           └─> jhgan/ko-sroberta-multitask
        │   │
        │   └─> BM25 검색
        │       ├─> _get_bm25_retriever()
        │       └─> _tokenize_korean()
        │           └─> kiwipiepy (한국어 형태소 분석)
        │
        ├─> 4단계: 점수 결합
        │   └─> 벡터 주 점수 + BM25 보정
        │
        ├─> 5단계: Threshold 체크
        │
        └─> 6단계: Reranking (선택적)
            └─> _rerank_documents()
                └─> sentence_transformers.CrossEncoder
                    └─> Dongjin-kr/ko-reranker
```

### 8. 설정 파일 연결

```
app/core/config.py
    ├─> .env 파일 읽기
    │   └─> dotenv.load_dotenv()
    │
    └─> Settings 클래스
        ├─> database_url
        ├─> openai_api_key
        ├─> use_lm_studio
        ├─> vector_db_path
        ├─> embedding_model
        ├─> enable_hybrid_search
        └─> enable_reranking
            │
            ▼
사용하는 모든 모듈
    ├─> app/main.py
    ├─> app/core/database.py
    ├─> ai_engine/graph/nodes/*.py
    ├─> ai_engine/vector_store.py
    └─> ...
```

### 9. 프론트엔드 연결

```
frontend/src/
    │
    ├─> main.tsx
    │   └─> App.tsx 렌더링
    │
    ├─> App.tsx
    │   ├─> ChatWindow 컴포넌트
    │   └─> HandoverModal 컴포넌트
    │
    ├─> components/ChatWindow.tsx
    │   ├─> ChatMessage 컴포넌트 (메시지 표시)
    │   ├─> ChatInput 컴포넌트 (입력)
    │   └─> chatApi.sendMessage() 호출
    │       │
    │       └─> services/api.ts
    │           └─> axios.post('/api/v1/chat/message')
    │
    └─> types/api.ts
        └─> TypeScript 타입 정의
            ├─> ChatRequest
            ├─> ChatResponse
            ├─> HandoverRequest
            └─> HandoverResponse
```

### 10. 스키마 및 타입 연결

```
app/schemas/
    │
    ├─> common.py
    │   └─> Enum 정의
    │       ├─> IntentType
    │       ├─> ActionType
    │       ├─> SentimentType
    │       └─> TriageDecisionType
    │
    ├─> chat.py
    │   ├─> ChatRequest (Pydantic)
    │   └─> ChatResponse (Pydantic)
    │
    └─> handover.py
        ├─> HandoverRequest (Pydantic)
        └─> HandoverResponse (Pydantic)
            │
            ▼
사용하는 곳:
    ├─> app/api/v1/chat.py
    ├─> app/api/v1/handover.py
    ├─> app/services/workflow_service.py
    ├─> ai_engine/graph/state.py (타입 참조)
    └─> ai_engine/graph/nodes/*.py
```

---

## 📊 모듈 간 의존성 요약

### 백엔드 계층 구조

```
┌─────────────────────────────────────────┐
│         API Layer (FastAPI)             │
│  - app/api/v1/chat.py                   │
│  - app/api/v1/handover.py               │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       Service Layer                     │
│  - app/services/workflow_service.py     │
│  - app/services/session_manager.py      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│        AI Engine Layer                  │
│  - ai_engine/graph/workflow.py          │
│  - ai_engine/graph/nodes/*.py           │
│  - ai_engine/graph/tools/*.py           │
│  - ai_engine/vector_store.py            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Infrastructure Layer               │
│  - app/core/database.py                 │
│  - app/core/config.py                   │
│  - app/models/*.py                      │
│  - ChromaDB                             │
│  - MySQL/MariaDB                        │
└─────────────────────────────────────────┘
```

### 주요 의존성 패턴

1. **상향 의존성**: 하위 계층은 상위 계층을 모름
   - `database.py`는 `api.py`를 모름
   - `nodes/*.py`는 `api.py`를 모름

2. **설정 주입**: 모든 모듈이 `config.py`의 `settings` 사용

3. **상태 전달**: `GraphState`를 통해 노드 간 데이터 전달

4. **Tool 패턴**: 기능을 Tool로 분리하여 재사용

---

## 🔄 데이터 흐름 요약

### 일반 질문 처리
```
User Message
    ↓
API (chat.py)
    ↓
Workflow Service
    ↓
GraphState 생성
    ↓
Triage Agent
    ├─> Intent Classification
    ├─> RAG Search
    └─> Decision: AUTO_HANDLE_OK
    ↓
Answer Agent
    └─> 답변 생성
    ↓
Chat DB Storage
    └─> DB 저장
    ↓
Response 반환
```

### 상담사 이관 처리
```
User Message ("상담사 연결")
    ↓
Triage Agent
    └─> Decision: HUMAN_REQUIRED
    ↓
Answer Agent
    └─> "상담사 연결하시겠습니까?"
    ↓
User: "예"
    ↓
Answer Agent
    └─> is_collecting_info = True
    ↓
정보 수집 질문 5회
    ↓
6번째 턴
    ↓
Summary Agent
    └─> 대화 요약
    ↓
Human Transfer
    └─> 이관 정보 생성
    ↓
Chat DB Storage
    └─> DB 저장
    ↓
Response 반환
```

---

## 🎯 핵심 연결점

### 1. API ↔ Service
- **파일**: `app/api/v1/chat.py` ↔ `app/services/workflow_service.py`
- **연결**: `process_chat_message()` 호출
- **데이터**: `ChatRequest` → `ChatResponse`

### 2. Service ↔ Workflow
- **파일**: `app/services/workflow_service.py` ↔ `ai_engine/graph/workflow.py`
- **연결**: `get_workflow().ainvoke(state)`
- **데이터**: `GraphState` 주고받음

### 3. Workflow ↔ Nodes
- **파일**: `ai_engine/graph/workflow.py` ↔ `ai_engine/graph/nodes/*.py`
- **연결**: 노드 함수 직접 호출
- **데이터**: `GraphState` 주고받음

### 4. Nodes ↔ Tools
- **파일**: `ai_engine/graph/nodes/triage_agent.py` ↔ `ai_engine/graph/tools/*.py`
- **연결**: `tool.invoke()` 호출
- **데이터**: Dict 입력/출력

### 5. Tools ↔ Vector Store
- **파일**: `ai_engine/graph/tools/rag_search_tool.py` ↔ `ai_engine/vector_store.py`
- **연결**: `search_documents()` 함수 호출
- **데이터**: query 문자열 → 검색 결과 리스트

### 6. Service ↔ Database
- **파일**: `app/services/session_manager.py` ↔ `app/core/database.py`
- **연결**: `SessionLocal()` 사용
- **데이터**: `ConversationMessage` 리스트

### 7. Nodes ↔ Database
- **파일**: `ai_engine/graph/nodes/chat_db_storage.py` ↔ `app/core/database.py`
- **연결**: `SessionLocal()` 사용
- **데이터**: `ChatSession`, `ChatMessage` 저장

---

## 📝 참고사항

1. **의존성 방향**: 항상 하위 계층 → 상위 계층 방향
2. **상태 관리**: `GraphState`가 워크플로우 전체 상태를 관리
3. **비동기 처리**: FastAPI의 async/await 패턴 사용
4. **싱글톤 패턴**: `settings`, `session_manager`, `_workflow` 등
5. **설정 주입**: 모든 모듈이 `.env` 파일의 설정을 `config.py`를 통해 사용

