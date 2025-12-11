# 벡터 DB 설정 및 사용 가이드

이 문서는 RAG 검색을 위한 벡터 DB(ChromaDB) 설정 및 사용 방법을 설명합니다.

## 목차
1. [설치](#설치)
2. [설정](#설정)
3. [문서 추가](#문서-추가)
4. [검색 사용](#검색-사용)
5. [문제 해결](#문제-해결)

## 설치

### 1. 필요한 패키지 설치

```bash
pip install -r requirements.txt
```

주요 패키지:
- `chromadb`: 벡터 DB
- `langchain-community`: LangChain 통합
- `sentence-transformers`: 한국어 임베딩 모델

### 2. 임베딩 모델 자동 다운로드

첫 실행 시 `paraphrase-multilingual-MiniLM-L12-v2` 모델이 자동으로 다운로드됩니다.
(약 420MB, 인터넷 연결 필요)

## 설정

### 환경 변수 설정 (선택사항)

`.env` 파일에 다음 설정을 추가할 수 있습니다:

```env
# 벡터 DB 저장 경로 (기본값: ./chroma_db)
VECTOR_DB_PATH=./chroma_db

# 임베딩 모델 (기본값: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# 컬렉션 이름 (기본값: financial_documents)
COLLECTION_NAME=financial_documents
```

### 설정 파일 위치

설정은 `app/core/config.py`에서 관리됩니다:

```python
# 벡터 DB 설정 (ChromaDB)
vector_db_path: str = "./chroma_db"
embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
collection_name: str = "financial_documents"
```

## 문서 추가

### 방법 1: 스크립트 사용 (권장)

예제 스크립트를 실행하여 문서를 추가할 수 있습니다:

```bash
python scripts/add_documents_to_vector_db.py
```

### 방법 2: Python 코드에서 직접 추가

```python
from ai_engine.vector_store import add_documents

# 문서 텍스트와 메타데이터 준비
texts = [
    "대출 금리는 연 2.5% ~ 4.5%입니다...",
    "예금 금리는 연 3.0% ~ 3.5%입니다...",
]

metadatas = [
    {"source": "대출안내서.pdf", "page": 1, "category": "대출"},
    {"source": "예금안내서.pdf", "page": 1, "category": "예금"},
]

# 벡터 DB에 추가
ids = add_documents(
    texts=texts,
    metadatas=metadatas,
    chunk_size=1000,      # 청크 크기
    chunk_overlap=200     # 청크 겹침
)
```

### 방법 3: PDF 파일에서 문서 로드

```python
from ai_engine.ingestion.loader import load_documents
from ai_engine.vector_store import add_documents

# PDF 파일 로드 (loader.py에 구현 필요)
documents = load_documents("path/to/document.pdf")

# 텍스트와 메타데이터 추출
texts = [doc.page_content for doc in documents]
metadatas = [doc.metadata for doc in documents]

# 벡터 DB에 추가
add_documents(texts=texts, metadatas=metadatas)
```

## 검색 사용

### RAG 검색 도구 사용

`rag_search_tool.py`의 `search_rag_documents` 함수를 사용합니다:

```python
from ai_engine.graph.tools.rag_search_tool import search_rag_documents, parse_rag_result

# 검색 실행
result_json = search_rag_documents("대출 금리는 얼마인가요?", top_k=5)

# 결과 파싱
documents = parse_rag_result(result_json)

# 결과 사용
for doc in documents:
    print(f"출처: {doc['source']}, 점수: {doc['score']}")
    print(f"내용: {doc['content']}")
```

### 직접 벡터 스토어 사용

```python
from ai_engine.vector_store import search_documents

# 검색 실행
results = search_documents(
    query="대출 금리",
    top_k=5,
    score_threshold=0.5  # 최소 유사도 점수
)

# 결과 확인
for result in results:
    print(f"점수: {result['score']}")
    print(f"출처: {result['source']}")
    print(f"내용: {result['content']}")
```

### LangChain Retriever 사용

```python
from ai_engine.vector_store import get_retriever

# Retriever 생성
retriever = get_retriever(k=5, score_threshold=0.5)

# 검색 실행
docs = retriever.get_relevant_documents("대출 금리")
```

## 워크플로우에서 사용

RAG 검색은 LangGraph 워크플로우의 노드에서 자동으로 사용됩니다:

```python
# workflow.py 또는 노드 파일에서
from ai_engine.graph.tools.rag_search_tool import (
    rag_search_tool,
    parse_rag_result,
    get_best_score,
    is_low_confidence
)

# 검색 실행
result_json = rag_search_tool.invoke({
    "query": state["user_message"],
    "top_k": 5
})

# 결과 파싱
documents = parse_rag_result(result_json)

# 신뢰도 확인
best_score = get_best_score(documents)
low_confidence = is_low_confidence(documents)
```

## 문제 해결

### 1. 벡터 DB 초기화 오류

**문제**: `chromadb` 연결 오류

**해결**:
- 벡터 DB 경로에 쓰기 권한이 있는지 확인
- `chroma_db` 디렉토리를 삭제하고 다시 생성

```python
from ai_engine.vector_store import reset_vector_store
reset_vector_store()
```

### 2. 임베딩 모델 다운로드 실패

**문제**: 모델 다운로드 중 네트워크 오류

**해결**:
- 인터넷 연결 확인
- Hugging Face 토큰 설정 (필요시)
- 다른 모델 사용:

```python
# config.py에서 변경
embedding_model: str = "sentence-transformers/distiluse-base-multilingual-cased"
```

### 3. 검색 결과가 없음

**문제**: `search_documents`가 빈 리스트 반환

**해결**:
- 벡터 DB에 문서가 추가되었는지 확인
- `score_threshold` 값을 낮춤 (기본값: 0.0)
- 쿼리 텍스트를 더 구체적으로 작성

### 4. 메모리 부족

**문제**: 대용량 문서 추가 시 메모리 오류

**해결**:
- `chunk_size`를 작게 설정 (예: 500)
- 배치로 나누어 추가
- GPU 사용 시 `vector_store.py`에서 `device="cuda"` 설정

## 고급 설정

### GPU 사용

`ai_engine/vector_store.py`에서:

```python
_embeddings = HuggingFaceEmbeddings(
    model_name=settings.embedding_model,
    model_kwargs={"device": "cuda"},  # GPU 사용
    encode_kwargs={"normalize_embeddings": True}
)
```

### 다른 벡터 DB 사용

ChromaDB 대신 다른 벡터 DB를 사용하려면 `vector_store.py`를 수정:

- **FAISS**: 메모리 기반, 빠른 검색
- **Qdrant**: 로컬/클라우드, 고성능
- **Pinecone**: 완전 관리형 클라우드 서비스

## 참고 자료

- [ChromaDB 문서](https://docs.trychroma.com/)
- [LangChain 벡터 스토어](https://python.langchain.com/docs/modules/data_connection/vectorstores/)
- [Sentence Transformers](https://www.sbert.net/)

