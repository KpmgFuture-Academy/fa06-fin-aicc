# LM Studio 설정 가이드

## LM Studio란?

LM Studio는 로컬에서 LLM 모델을 실행할 수 있게 해주는 도구입니다. OpenAI API 대신 로컬 모델을 사용하여 비용 없이 챗봇을 테스트할 수 있습니다.

## 설정 방법

### 1. LM Studio 설치

1. [LM Studio 공식 사이트](https://lmstudio.ai/)에서 다운로드
2. 설치 후 LM Studio 실행

### 2. 모델 다운로드

1. LM Studio에서 `Search` 탭으로 이동
2. `openai/gpt-oss-20b` 모델 검색
3. 모델 다운로드

### 3. 모델 실행

1. LM Studio에서 `Chat` 탭으로 이동
2. 다운로드한 모델 선택
3. `Start Server` 버튼 클릭
4. 서버가 `http://localhost:1234`에서 실행되는지 확인

### 4. 환경 변수 설정

프로젝트 루트의 `.env` 파일에 다음 설정 추가:

```env
# LM Studio 설정
USE_LM_STUDIO=true
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=openai/gpt-oss-20b

# OpenAI 설정 (LM Studio 사용 시 필요 없음)
# OPENAI_API_KEY=sk-your-api-key-here
```

### 5. 서버 재시작

백엔드 서버를 재시작하세요:

```powershell
# 서버 중지 (Ctrl+C)
# 서버 재시작
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

## 설정 옵션

### LM Studio 사용 (기본값)

```env
USE_LM_STUDIO=true
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=openai/gpt-oss-20b
```

### OpenAI API 사용

```env
USE_LM_STUDIO=false
OPENAI_API_KEY=sk-your-api-key-here
```

## 문제 해결

### LM Studio 서버에 연결할 수 없음

1. LM Studio가 실행 중인지 확인
2. `http://localhost:1234`에 접속 가능한지 확인
3. LM Studio에서 서버가 시작되었는지 확인

### 모델을 찾을 수 없음

1. LM Studio에서 모델이 다운로드되었는지 확인
2. 모델 이름이 정확한지 확인 (`openai/gpt-oss-20b`)
3. 다른 모델을 사용하려면 `.env` 파일의 `LM_STUDIO_MODEL` 변경

### 응답이 느림

- 로컬 모델은 GPU가 없으면 느릴 수 있습니다
- 더 작은 모델을 사용하거나 GPU 가속을 활성화하세요

## 모델 변경

다른 모델을 사용하려면 `.env` 파일에서 모델 이름을 변경:

```env
LM_STUDIO_MODEL=your-model-name
```

예시:
- `openai/gpt-oss-20b`
- `microsoft/Phi-3-mini-4k-instruct`
- `Qwen/Qwen2.5-7B-Instruct`

## 장점

- ✅ 비용 없음 (로컬 실행)
- ✅ 인터넷 연결 불필요
- ✅ 데이터 프라이버시 (로컬 처리)
- ✅ 무제한 사용

## 단점

- ⚠️ GPU가 없으면 느릴 수 있음
- ⚠️ 모델 크기에 따라 많은 메모리 필요
- ⚠️ 모델 품질이 OpenAI API보다 낮을 수 있음

