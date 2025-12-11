# 프론트엔드-백엔드 검증 체크리스트

프론트엔드와 백엔드가 설계대로 잘 처리되고 있는지 확인하는 방법입니다.

## 📋 목차
1. [API 엔드포인트 검증](#1-api-엔드포인트-검증)
2. [데이터 스키마 일치 확인](#2-데이터-스키마-일치-확인)
3. [워크플로우 검증](#3-워크플로우-검증)
4. [통합 테스트 방법](#4-통합-테스트-방법)
5. [자동화 테스트 스크립트](#5-자동화-테스트-스크립트)

---

## 1. API 엔드포인트 검증

### 1.1 백엔드 API 엔드포인트 확인

백엔드 서버가 실행 중인지 확인:
```bash
# 백엔드 디렉토리로 이동
cd fa06-fin-aicc

# 서버 실행 (별도 터미널)
uvicorn app.main:app --reload --port 8000
```

**확인 사항:**
- ✅ `GET http://localhost:8000/` → 서버 상태 확인
- ✅ `GET http://localhost:8000/health` → 헬스체크 (DB 연결 포함)
- ✅ `GET http://localhost:8000/docs` → Swagger UI 문서 확인

### 1.2 프론트엔드 API 호출 확인

프론트엔드가 올바른 엔드포인트를 호출하는지 확인:

**백엔드 엔드포인트:**
- `POST /api/v1/chat/message` (chat.py)
- `POST /api/v1/handover/analyze` (handover.py)

**프론트엔드 API 호출:**
- `frontend/src/services/api.ts`의 `chatApi.sendMessage()`
- `frontend/src/services/api.ts`의 `chatApi.requestHandover()`

**확인 방법:**
1. 브라우저 개발자 도구 (F12) → Network 탭 열기
2. 채팅 메시지 전송
3. 요청 URL이 `http://localhost:8000/api/v1/chat/message`인지 확인
4. 요청 헤더에 `Content-Type: application/json`이 있는지 확인

---

## 2. 데이터 스키마 일치 확인

### 2.1 ChatRequest/ChatResponse 스키마

**백엔드 스키마** (`app/schemas/chat.py`):
```python
class ChatRequest:
    session_id: str
    user_message: str

class ChatResponse:
    ai_message: str
    intent: IntentType  # INFO_REQ, COMPLAINT, HUMAN_REQ
    suggested_action: ActionType  # CONTINUE, HANDOVER
    source_documents: List[SourceDocument]
```

**프론트엔드 타입** (`frontend/src/types/api.ts`):
```typescript
interface ChatRequest {
  session_id: string;
  user_message: string;
}

interface ChatResponse {
  ai_message: string;
  intent: IntentType;  // 'INFO_REQ' | 'COMPLAINT' | 'HUMAN_REQ'
  suggested_action: ActionType;  // 'CONTINUE' | 'HANDOVER'
  source_documents: SourceDocument[];
}
```

**확인 체크리스트:**
- ✅ 필드 이름이 정확히 일치하는가? (snake_case vs camelCase)
- ✅ 필수 필드가 모두 포함되어 있는가?
- ✅ 타입이 일치하는가? (str ↔ string, List ↔ Array)

### 2.2 HandoverRequest/HandoverResponse 스키마

**백엔드 스키마** (`app/schemas/handover.py`):
```python
class HandoverRequest:
    session_id: str
    trigger_reason: str

class HandoverResponse:
    status: str
    analysis_result: AnalysisResult
        - customer_sentiment: SentimentType
        - summary: str
        - extracted_keywords: List[str]
        - kms_recommendations: List[KMSRecommendation]
```

**프론트엔드 타입** (`frontend/src/types/api.ts`):
```typescript
interface HandoverRequest {
  session_id: string;
  trigger_reason: string;
}

interface HandoverResponse {
  status: string;
  analysis_result: AnalysisResult;
    - customer_sentiment: SentimentType;
    - summary: string;
    - extracted_keywords: string[];
    - kms_recommendations: KMSRecommendation[];
}
```

**확인 방법:**
1. Swagger UI (`http://localhost:8000/docs`)에서 스키마 확인
2. 실제 API 응답을 브라우저 개발자 도구에서 확인
3. TypeScript 타입 에러가 없는지 확인

---

## 3. 워크플로우 검증

### 3.1 채팅 메시지 처리 흐름

**설계된 흐름:**
```
사용자 메시지 입력
  ↓
프론트엔드: chatApi.sendMessage() 호출
  ↓
백엔드: POST /api/v1/chat/message
  ↓
workflow_service.process_chat_message()
  ↓
LangGraph 워크플로우 실행
  - decision_agent (의도 분류)
  - answer_agent 또는 summary_agent
  ↓
DB에 메시지 저장
  ↓
ChatResponse 반환
  ↓
프론트엔드: 메시지 UI에 표시
```

**검증 방법:**
1. **백엔드 로그 확인:**
   ```bash
   # 백엔드 터미널에서 로그 확인
   # 다음과 같은 로그가 순서대로 나타나야 함:
   # - "=== API 엔드포인트 도달: /api/v1/chat/message ==="
   # - "채팅 메시지 수신 - 세션: ..."
   # - "채팅 메시지 처리 완료 - 세션: ..."
   ```

2. **프론트엔드 콘솔 확인:**
   - 브라우저 개발자 도구 → Console 탭
   - `console.log('API 호출 시작:', ...)` 메시지 확인
   - `console.log('API 응답 받음:', response)` 메시지 확인

3. **데이터베이스 확인:**
   ```sql
   -- 채팅 메시지가 DB에 저장되었는지 확인
   SELECT * FROM chat_messages ORDER BY created_at DESC LIMIT 10;
   ```

### 3.2 상담원 이관 처리 흐름

**설계된 흐름:**
```
사용자가 "상담원 연결" 버튼 클릭
  ↓
프론트엔드: chatApi.requestHandover() 호출
  ↓
백엔드: POST /api/v1/handover/analyze
  ↓
workflow_service.process_handover()
  ↓
세션의 전체 대화 이력 로드
  ↓
summary_agent로 요약 생성
  ↓
HandoverResponse 반환 (감정 분석, 키워드, KMS 추천 포함)
  ↓
프론트엔드: HandoverModal에 결과 표시
```

**검증 방법:**
1. 채팅을 여러 번 주고받은 후 상담원 이관 버튼 클릭
2. HandoverModal이 올바른 데이터를 표시하는지 확인
3. 백엔드 로그에서 "상담원 이관 처리 완료" 메시지 확인

---

## 4. 통합 테스트 방법

### 4.1 수동 테스트 시나리오

#### 시나리오 1: 기본 채팅 테스트
1. 프론트엔드 실행: `cd frontend && npm run dev`
2. 브라우저에서 `http://localhost:5173` 접속
3. 채팅 입력창에 "대출 금리 얼마야?" 입력
4. **확인 사항:**
   - ✅ AI 응답이 표시되는가?
   - ✅ 응답에 `intent`와 `suggested_action`이 포함되어 있는가?
   - ✅ `source_documents`가 있는 경우 표시되는가?
   - ✅ 브라우저 콘솔에 에러가 없는가?

#### 시나리오 2: 상담원 이관 테스트
1. 여러 번 채팅을 주고받음
2. "상담원 연결" 버튼 클릭
3. **확인 사항:**
   - ✅ HandoverModal이 열리는가?
   - ✅ 요약(summary)이 표시되는가?
   - ✅ 감정 분석(customer_sentiment)이 표시되는가?
   - ✅ 키워드(extracted_keywords)가 표시되는가?
   - ✅ KMS 추천 문서가 표시되는가?

#### 시나리오 3: 에러 처리 테스트
1. 백엔드 서버를 중지
2. 프론트엔드에서 메시지 전송 시도
3. **확인 사항:**
   - ✅ 적절한 에러 메시지가 표시되는가?
   - ✅ "백엔드 서버에 연결할 수 없습니다" 같은 친화적인 메시지인가?

### 4.2 API 직접 테스트 (Postman/curl)

#### 채팅 메시지 테스트
```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "user_message": "대출 금리 얼마야?"
  }'
```

**예상 응답:**
```json
{
  "ai_message": "대출 금리에 대해 안내드리겠습니다...",
  "intent": "INFO_REQ",
  "suggested_action": "CONTINUE",
  "source_documents": [
    {
      "source": "loan_guide.pdf",
      "page": 5,
      "score": 0.85
    }
  ]
}
```

#### 상담원 이관 테스트
```bash
curl -X POST http://localhost:8000/api/v1/handover/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "trigger_reason": "USER_REQUEST"
  }'
```

**예상 응답:**
```json
{
  "status": "success",
  "analysis_result": {
    "customer_sentiment": "NEUTRAL",
    "summary": "고객이 대출 금리에 대해 문의했습니다...",
    "extracted_keywords": ["대출", "금리", "문의"],
    "kms_recommendations": [
      {
        "title": "대출 상품 안내",
        "url": "https://example.com/loan",
        "relevance_score": 0.9
      }
    ]
  }
}
```

---

## 5. 자동화 테스트 스크립트

### 5.1 Python 테스트 스크립트

`test_api_integration.py` 파일을 생성하여 자동 테스트:

```python
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health_check():
    """헬스체크 테스트"""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✅ 헬스체크 통과")

def test_chat_message():
    """채팅 메시지 테스트"""
    session_id = f"test_session_{int(time.time())}"
    payload = {
        "session_id": session_id,
        "user_message": "대출 금리 얼마야?"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/message",
        json=payload,
        timeout=60
    )
    assert response.status_code == 200
    data = response.json()
    
    # 스키마 검증
    assert "ai_message" in data
    assert "intent" in data
    assert "suggested_action" in data
    assert "source_documents" in data
    assert data["intent"] in ["INFO_REQ", "COMPLAINT", "HUMAN_REQ"]
    assert data["suggested_action"] in ["CONTINUE", "HANDOVER"]
    
    print(f"✅ 채팅 메시지 테스트 통과: intent={data['intent']}")
    return session_id

def test_handover(session_id):
    """상담원 이관 테스트"""
    payload = {
        "session_id": session_id,
        "trigger_reason": "USER_REQUEST"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/handover/analyze",
        json=payload,
        timeout=60
    )
    assert response.status_code == 200
    data = response.json()
    
    # 스키마 검증
    assert "status" in data
    assert "analysis_result" in data
    analysis = data["analysis_result"]
    assert "customer_sentiment" in analysis
    assert "summary" in analysis
    assert "extracted_keywords" in analysis
    assert "kms_recommendations" in analysis
    
    print(f"✅ 상담원 이관 테스트 통과: sentiment={analysis['customer_sentiment']}")

if __name__ == "__main__":
    print("🧪 API 통합 테스트 시작...\n")
    
    try:
        test_health_check()
        session_id = test_chat_message()
        test_handover(session_id)
        print("\n✅ 모든 테스트 통과!")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        raise
```

### 5.2 실행 방법

```bash
# 백엔드 서버가 실행 중이어야 함
cd fa06-fin-aicc
python test_api_integration.py
```

---

## 6. 체크리스트 요약

### 백엔드 검증
- [ ] 서버가 정상적으로 시작되는가?
- [ ] `/health` 엔드포인트가 정상 동작하는가?
- [ ] `/api/v1/chat/message` 엔드포인트가 올바른 스키마로 응답하는가?
- [ ] `/api/v1/handover/analyze` 엔드포인트가 올바른 스키마로 응답하는가?
- [ ] 에러 발생 시 적절한 HTTP 상태 코드를 반환하는가?
- [ ] 로그가 적절히 기록되는가?

### 프론트엔드 검증
- [ ] API 호출이 올바른 엔드포인트로 전송되는가?
- [ ] 요청 본문이 올바른 형식인가?
- [ ] 응답 데이터를 올바르게 파싱하는가?
- [ ] 에러 처리가 적절한가?
- [ ] UI가 응답 데이터를 올바르게 표시하는가?
- [ ] TypeScript 타입 에러가 없는가?

### 통합 검증
- [ ] 프론트엔드와 백엔드가 올바르게 통신하는가?
- [ ] 세션 관리가 올바르게 동작하는가?
- [ ] 데이터베이스에 메시지가 저장되는가?
- [ ] 워크플로우가 설계대로 실행되는가?

---

## 7. 문제 해결 가이드

### 문제: CORS 에러
**증상:** 브라우저 콘솔에 "CORS policy" 에러
**해결:** `app/main.py`의 CORS 설정 확인

### 문제: 타임아웃 에러
**증상:** "응답 생성에 시간이 오래 걸리고 있습니다" 메시지
**해결:** 
- `frontend/src/services/api.ts`의 `API_TIMEOUT` 값 확인
- LM Studio가 실행 중인지 확인

### 문제: 스키마 불일치
**증상:** TypeScript 타입 에러 또는 런타임 에러
**해결:**
1. `app/schemas/chat.py`와 `frontend/src/types/api.ts` 비교
2. 필드 이름과 타입이 일치하는지 확인

### 문제: 세션 관리 오류
**증상:** 이전 대화 내용이 유지되지 않음
**해결:**
1. `frontend/src/utils/session.ts` 확인
2. `app/services/session_manager.py` 확인
3. 데이터베이스에 메시지가 저장되는지 확인

---

## 8. 추가 확인 사항

### 성능 확인
- [ ] API 응답 시간이 적절한가? (일반적으로 5초 이내)
- [ ] 프론트엔드 로딩 상태가 적절히 표시되는가?

### 보안 확인
- [ ] 민감한 정보가 로그에 노출되지 않는가?
- [ ] 입력 검증이 적절히 이루어지는가?

### 사용자 경험 확인
- [ ] 에러 메시지가 사용자 친화적인가?
- [ ] 로딩 중 적절한 피드백이 제공되는가?
- [ ] 모바일 환경에서도 잘 동작하는가?

