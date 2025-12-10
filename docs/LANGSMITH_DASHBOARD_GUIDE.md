# LangSmith 대시보드 사용 가이드

## 🎯 목표
LangSmith 대시보드에서 프롬프트 디버깅을 시작하는 방법을 단계별로 안내합니다.

---

## 1단계: LangSmith 대시보드 접속

1. **웹 브라우저에서 [LangSmith 대시보드](https://smith.langchain.com/) 접속**
2. **로그인** (GitHub 또는 이메일 계정)

---

## 2단계: 프로젝트 찾기

### 방법 1: 프로젝트 메뉴에서 찾기

1. 좌측 사이드바에서 **"Projects"** 클릭
2. 프로젝트 목록에서 **"bank-aicc-prompt-debugging"** 찾기
   - 만약 보이지 않으면, 아직 trace가 한 번도 전송되지 않은 것입니다
   - 이 경우 다음 단계로 넘어가서 LLM 호출을 먼저 해야 합니다

### 방법 2: 직접 URL로 접속

```
https://smith.langchain.com/o/[your-org-id]/projects/p/bank-aicc-prompt-debugging
```

(실제 URL은 로그인 후 주소창에서 확인 가능)

---

## 3단계: 첫 번째 Trace 생성하기

LangSmith에 trace가 나타나려면 **실제 LLM 호출**이 발생해야 합니다.

### 옵션 A: 음성 챗봇 사용 (프론트엔드 실행)

1. 프론트엔드 애플리케이션 실행
2. 음성 또는 텍스트로 메시지 전송
   - 예: "카드 연회비는 얼마인가요?"
   - 예: "할인 혜택이 뭐가 있나요?"

### 옵션 B: API 직접 호출 (터미널)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "user_message": "카드 연회비는 얼마인가요?"
  }'
```

### 옵션 C: Python 스크립트로 테스트

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/chat",
    json={
        "session_id": "test-session-123",
        "user_message": "카드 연회비는 얼마인가요?"
    }
)
print(response.json())
```

---

## 4단계: Trace 확인하기

### 4.1 대시보드 새로고침

1. LangSmith 대시보드에서 **"Traces"** 탭 클릭
2. 페이지 **새로고침** (F5 또는 Ctrl+R)
3. 최근 실행된 trace가 목록에 나타납니다

### 4.2 Trace 목록 이해하기

각 trace는 다음 정보를 보여줍니다:
- **Timestamp**: 실행 시간
- **Name**: 실행 이름 (예: "ChatOpenAI", "AgentExecutor")
- **Latency**: 실행 시간 (ms)
- **Tokens**: 사용된 토큰 수
- **Status**: 성공/실패 여부

---

## 5단계: Trace 상세 정보 확인하기

### 5.1 Trace 클릭

목록에서 trace를 클릭하면 상세 정보가 열립니다.

### 5.2 확인할 수 있는 정보

#### 📥 입력 (Input)
- **System Prompt**: 시스템 프롬프트 전체 내용
- **User Message**: 고객의 실제 입력
- **Context**: RAG 검색 결과, 의도 분류 결과 등

#### 📤 출력 (Output)
- **LLM Response**: 생성된 답변
- **Token Usage**: 
  - Input tokens
  - Output tokens
  - Total tokens

#### ⏱️ 성능 정보
- **Latency**: 전체 실행 시간
- **각 단계별 시간**: 
  - Triage Agent 실행 시간
  - RAG 검색 시간
  - Answer Agent 실행 시간

#### 🔧 중간 단계 (Steps)
- **Tool Calls**: 의도 분류, RAG 검색 등 도구 호출
- **각 노드의 입력/출력**: LangGraph의 각 노드별 상태

---

## 6단계: 프롬프트 디버깅하기

### 6.1 문제 발견

예를 들어:
- ❌ 부적절한 답변
- ❌ 잘못된 티켓 분류
- ❌ RAG 검색 결과 미활용

### 6.2 프롬프트 분석

1. **입력 확인**: System Prompt와 User Message가 올바른지 확인
2. **출력 확인**: LLM이 어떻게 응답했는지 확인
3. **중간 단계 확인**: RAG 검색 결과가 제대로 전달되었는지 확인

### 6.3 프롬프트 수정

문제를 발견했다면:

1. **프롬프트 파일 열기**:
   - `fa06-fin-aicc/ai_engine/prompts/templates.py` (RAG 답변)
   - `fa06-fin-aicc/ai_engine/graph/nodes/triage_agent.py` (티켓 분류)
   - `fa06-fin-aicc/ai_engine/graph/nodes/answer_agent.py` (답변 생성)

2. **프롬프트 수정**

3. **애플리케이션 재시작** (필요시)

4. **동일한 입력으로 재테스트**

5. **LangSmith에서 새 trace 확인**

### 6.4 버전 비교

LangSmith의 **"Compare"** 기능을 사용하여:
- 이전 프롬프트 버전과 새 버전 비교
- 성능 개선 여부 확인
- 토큰 사용량 비교

---

## 7단계: 고급 기능 활용

### 7.1 필터링

- **시간 범위**: 특정 기간의 trace만 보기
- **Status**: 성공/실패만 필터링
- **Tags**: 커스텀 태그로 필터링

### 7.2 검색

- **Trace 이름으로 검색**: 특정 에이전트나 모델의 trace만 보기
- **입력/출력 내용으로 검색**: 특정 키워드가 포함된 trace 찾기

### 7.3 Dataset 생성

1. **"Datasets"** 탭 클릭
2. **"Create Dataset"** 클릭
3. 테스트 케이스 추가:
   - Input: 고객 질문
   - Expected Output: 기대하는 답변
4. **"Evaluations"** 탭에서 자동 평가 실행

### 7.4 Playground에서 실험

1. **"Playground"** 탭 클릭
2. 프롬프트 템플릿 입력
3. 다양한 입력으로 실시간 테스트
4. Temperature, Max Tokens 등 파라미터 조정

---

## 8단계: 실전 디버깅 예시

### 시나리오: 답변이 부정확한 경우

1. **LangSmith에서 문제 trace 찾기**
   - Traces 탭에서 부정확한 답변이 있는 trace 클릭

2. **입력 확인**
   - System Prompt 확인
   - User Message 확인
   - RAG 검색 결과 확인 (Steps 탭)

3. **문제 분석**
   - RAG 검색 결과가 제대로 전달되었는가?
   - 프롬프트가 명확한가?
   - 지시사항이 충분한가?

4. **프롬프트 수정**
   ```python
   # templates.py 예시
   # 수정 전
   "참고 문서의 내용만 기반으로 답변하세요."
   
   # 수정 후
   "참고 문서의 내용만 기반으로 답변하세요. 문서에 없는 정보는 절대 추측하지 마세요."
   ```

5. **재테스트 및 비교**
   - 동일한 입력으로 재테스트
   - LangSmith에서 이전 trace와 비교

---

## 💡 유용한 팁

### 팁 1: 프로젝트별로 구분하기

다른 환경이나 목적에 따라 프로젝트를 분리:
```env
# 개발 환경
LANGSMITH_PROJECT=bank-aicc-dev

# 프롬프트 테스트
LANGSMITH_PROJECT=prompt-test-v1

# 프로덕션 모니터링
LANGSMITH_PROJECT=bank-aicc-production
```

### 팁 2: 자주 확인하는 Trace 북마크

중요한 trace는 북마크하여 나중에 쉽게 찾을 수 있습니다.

### 팁 3: 알림 설정

특정 조건(에러 발생, 긴 지연 시간 등)에 알림을 받도록 설정할 수 있습니다.

---

## ❓ 자주 묻는 질문

### Q: Trace가 보이지 않아요

**A:** 다음을 확인하세요:
1. LLM 호출이 실제로 발생했는지 확인
2. `.env` 파일에 `LANGSMITH_TRACING=true` 설정 확인
3. 애플리케이션 재시작 확인
4. 콘솔에 "✅ LangSmith 추적 활성화됨" 메시지 확인

### Q: 프로젝트가 보이지 않아요

**A:** 프로젝트는 첫 번째 trace가 전송될 때 자동으로 생성됩니다. LLM 호출을 한 번 실행한 후 새로고침하세요.

### Q: 모든 trace를 보고 싶어요

**A:** Traces 탭에서 시간 범위를 넓히거나, 필터를 제거하세요.

### Q: 특정 프롬프트만 추적하고 싶어요

**A:** 현재는 모든 LangChain 호출이 추적됩니다. 특정 부분만 추적하려면 코드 수정이 필요합니다.

---

## 🎉 다음 단계

이제 LangSmith에서 프롬프트 디버깅을 시작할 수 있습니다!

1. ✅ LangSmith 대시보드 접속
2. ✅ LLM 호출 테스트
3. ✅ Trace 확인
4. ✅ 프롬프트 분석 및 개선

**문제가 있거나 질문이 있으면 LangSmith 대시보드의 "Support" 또는 프로젝트 이슈 트래커를 활용하세요.**

