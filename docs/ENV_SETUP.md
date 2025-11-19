# 환경 변수 설정 가이드

프로젝트 루트 디렉토리에 `.env` 파일을 생성하여 다음 설정을 추가하세요.

## 필수 설정

### 1. 데이터베이스 설정

```env
# MySQL 데이터베이스 연결 URL
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/aicc_db?charset=utf8mb4
```

**설정 방법:**
- `root`: MySQL 사용자명
- `your_password`: MySQL 비밀번호
- `localhost:3306`: MySQL 서버 주소 및 포트
- `aicc_db`: 데이터베이스 이름

### 2. OpenAI API 키 (LM Studio 미사용 시)

```env
# OpenAI API 키 (.env 파일에서만 로드됨)
OPENAI_API_KEY=sk-proj-your-api-key-here
```

**중요:** 
- API 키는 반드시 `.env` 파일에 설정해야 합니다.
- 시스템 환경 변수는 무시됩니다.
- `.env` 파일은 Git에 커밋하지 마세요 (`.gitignore`에 포함됨)

### 3. LLM 설정

```env
# LM Studio 사용 여부 (true/false)
USE_LM_STUDIO=false

# LM Studio 설정 (USE_LM_STUDIO=true일 때만 사용)
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=openai/gpt-oss-20b

# LLM 호출 타임아웃 (초)
LLM_TIMEOUT=60  # OpenAI는 60초, LM Studio는 300초 이상 권장
```

### 4. 벡터 DB 설정 (ChromaDB)

```env
# ChromaDB 저장 경로
VECTOR_DB_PATH=./chroma_db

# 임베딩 모델 (한국어 지원)
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# ChromaDB 컬렉션 이름
COLLECTION_NAME=financial_documents
```

## 선택적 설정

### KoBERT 모델 경로

KoBERT 모델은 자동으로 다음 경로에서 탐색됩니다:
- `models/bert_intent_classifier/`
- 프로젝트 루트 기준 상대 경로

모델이 없으면 키워드 기반 fallback을 사용합니다.

## 전체 .env 파일 예시

```env
# 데이터베이스
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aicc_db?charset=utf8mb4

# OpenAI API (LM Studio 미사용 시)
OPENAI_API_KEY=sk-proj-your-api-key-here

# LLM 설정
USE_LM_STUDIO=false
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=openai/gpt-oss-20b
LLM_TIMEOUT=60

# 벡터 DB 설정
VECTOR_DB_PATH=./chroma_db
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
COLLECTION_NAME=financial_documents
```

## 설정 확인

서버 시작 시 다음 로그를 확인하세요:

```
INFO: 데이터베이스 연결 성공
INFO: ✅ OpenAI API 키 로드 완료 (길이: XX 문자)
INFO:   API 키 시작: sk-proj-...
INFO:   .env 파일에서 로드됨
```

또는 LM Studio 사용 시:

```
INFO: LM Studio 사용 - 모델: openai/gpt-oss-20b, URL: http://localhost:1234/v1
INFO: LM Studio가 실행 중인지 확인하세요: http://localhost:1234
```

## 문제 해결

### "OpenAI API 키가 설정되지 않았습니다" 오류
- `.env` 파일이 프로젝트 루트에 있는지 확인
- `OPENAI_API_KEY=sk-...` 형식이 올바른지 확인
- `.env` 파일에 공백이나 따옴표가 없는지 확인

### "데이터베이스 초기화 실패" 오류
- MySQL 서버가 실행 중인지 확인
- `DATABASE_URL` 형식이 올바른지 확인
- 데이터베이스가 생성되었는지 확인 (`setup_database.sql` 실행)

### "LM Studio 서버에 연결할 수 없습니다" 오류
- LM Studio가 실행 중인지 확인
- `LM_STUDIO_BASE_URL`이 올바른지 확인
- LM Studio 서버 포트가 1234인지 확인

### 벡터 DB 관련 오류
- `VECTOR_DB_PATH` 디렉토리가 생성 가능한지 확인
- 임베딩 모델이 다운로드되었는지 확인 (첫 실행 시 자동 다운로드)

