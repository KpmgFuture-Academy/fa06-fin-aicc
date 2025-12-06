# 🔍 상담원 대시보드 문제 해결

## 🐛 증상
상담원 대시보드 화면이 비어있고 이관 요청이 표시되지 않습니다.

## ✅ 수정 완료 사항

### 1. 메시지 처리 로직 개선
- 더 상세한 콘솔 로그 추가 (📩, ✅, ❌ 아이콘 사용)
- 데이터 구조 검증 강화
- 에러 핸들링 개선

### 2. Status 필드 충돌 해결
- `status` (HandoverResponse) ↔ `status` (처리 상태) 충돌 수정
- `processing_status`로 이름 변경하여 명확하게 구분

### 3. 네비게이션 버튼 추가
- **채팅 페이지**: "🔄 새 세션" 버튼 추가
- **상담원 대시보드**: "💬 채팅으로 돌아가기" 버튼 추가

---

## 🧪 테스트 방법

### 1단계: 브라우저 캐시 완전 삭제 ⭐

**매우 중요!** 이전 JavaScript 파일이 캐시되어 있을 수 있습니다.

#### Chrome/Edge:
```
1. F12 키를 눌러 개발자 도구 열기
2. 새로고침 버튼에서 마우스 오른쪽 클릭
3. "캐시 비우기 및 강력 새로고침" 선택
```

또는 **시크릿 모드**에서 테스트:
```
Ctrl + Shift + N (Chrome/Edge)
→ http://localhost:5173/consultant 접속
```

---

### 2단계: 상담원 대시보드 열기

```
http://localhost:5173/consultant
```

**브라우저 콘솔 확인 (F12 → 콘솔 탭):**

✅ **정상 연결**:
```
📩 상담원 대시보드 메시지 수신: { type: "status", message: "connected" }
ℹ️ 상태 메시지: connected
```

❌ **연결 실패**:
```
WebSocket connection to 'ws://localhost:8000/...' failed
```
→ 백엔드가 실행 중인지 확인하세요!

---

### 3단계: 새 창에서 채팅 시작

```
http://localhost:5173
```

---

### 4단계: 이관 요청 트리거

채팅창에서:
```
"상담원 연결해주세요"
```

그리고 동의 프로세스 진행:
```
1. "네" (동의)
2. "홍길동" (이름)
3. "네" (동의 다시)
```

---

### 5단계: 상담원 대시보드에서 로그 확인

**브라우저 콘솔 (F12)에서 다음 로그를 확인:**

✅ **성공 시**:
```
📩 상담원 대시보드 메시지 수신: { type: "handover_report", session_id: "sess_...", data: {...} }
✅ handover_report 타입 확인됨
📦 데이터: { status: "success", customer_sentiment: "NEUTRAL", ... }
🔑 세션 ID: sess_1234567890...
📝 생성된 리포트: { session_id: "sess_...", timestamp: ..., processing_status: "pending", ... }
📊 업데이트된 리포트 목록: 1 개
```

❌ **실패 시**:
```
⚠️ 알 수 없는 메시지 타입: xxx
또는
❌ message.data가 없습니다!
```

---

### 6단계: 대시보드 UI 확인

**좌측 목록:**
- 새 이관 요청 카드 표시됨
- 세션 ID (마지막 8자리)
- 고객 감정 아이콘 (😊😐😟🚨)
- 시간
- "시작하기" 버튼

**우측 상세 패널:**
- 카드 클릭 시 상세 정보 표시
- 고객 감정, 대화 요약, 핵심 키워드, KMS 문서

**상단 통계:**
- 전체, 대기, 진행, 완료 숫자 업데이트

---

## 🔧 여전히 문제가 있다면

### 1. 백엔드 로그 확인

터미널에서 다음 로그가 보여야 합니다:

```
INFO: WebSocket /api/v1/chat/ws/consultant_dashboard [accepted]
INFO: WebSocket 연결 수립 - 세션: consultant_dashboard, 현재 연결 수: X
INFO: 상담원 이관 감지 - 자동 리포트 생성 시작: sess_xxx
INFO: 상담원 대시보드로 브로드캐스트 - 대상: 1개
INFO: 상담원 리포트 자동 생성 완료 - 세션: sess_xxx
```

### 2. WebSocket 연결 확인

**브라우저 개발자 도구 → 네트워크 탭:**
1. "WS" 필터 선택
2. `ws://localhost:8000/api/v1/chat/ws/consultant_dashboard` 연결 확인
3. 상태가 "101 Switching Protocols"여야 함

### 3. 프론트엔드 재시작

```bash
cd frontend

# Vite 캐시 삭제
Remove-Item -Recurse -Force node_modules\.vite -ErrorAction SilentlyContinue

# 재시작
npm run dev
```

### 4. 백엔드 재시작

```bash
# Ctrl + C로 중지 후
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📸 스크린샷 요청 사항

문제가 지속되면 다음 스크린샷을 공유해주세요:

1. **상담원 대시보드 화면** (전체)
2. **브라우저 콘솔 (F12)** - 메시지 수신 로그
3. **네트워크 탭 (F12)** - WS 연결 상태
4. **백엔드 터미널 로그** - 브로드캐스트 메시지

---

## ✅ 새로 추가된 기능

### 1. 채팅 페이지
- **🔄 새 세션** 버튼: 대화 내용 초기화 및 새 세션 시작
- **🎧 상담원 대시보드** 버튼: 상담원 페이지로 이동

### 2. 상담원 대시보드
- **💬 채팅으로 돌아가기** 버튼: 메인 채팅 페이지로 복귀

---

## 🎯 기대 결과

### 정상 작동 시:

1. **상담원 대시보드 열림** → "📭 아직 이관 요청이 없습니다" 표시
2. **채팅에서 이관 요청** → 실시간으로 대시보드에 카드 추가
3. **카드 클릭** → 우측에 상세 정보 표시
4. **시작하기 버튼** → 상태가 "처리 중"으로 변경
5. **완료 처리 버튼** → 상태가 "완료"로 변경
6. **통계 업데이트** → 숫자 자동 변경

---

## 🚨 긴급 디버깅

### 콘솔에서 직접 테스트:

```javascript
// 1. WebSocket 연결 상태 확인
console.log('WebSocket 상태:', websocketService.ws?.readyState);
// 0: CONNECTING, 1: OPEN, 2: CLOSING, 3: CLOSED

// 2. 수동으로 테스트 메시지 전송
const testMessage = {
  type: 'handover_report',
  session_id: 'test_session_123',
  data: {
    status: 'success',
    customer_sentiment: 'POSITIVE',
    summary: '테스트 요약입니다.',
    extracted_keywords: ['테스트', '키워드'],
    kms_recommendations: []
  }
};

// 이 메시지를 수동으로 처리해보기
// (프론트엔드 코드에서 직접 호출)
```

---

**수정 완료! 테스트 후 결과를 알려주세요!** 🚀

