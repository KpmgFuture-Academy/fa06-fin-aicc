# 🔍 상담원 대시보드 데이터 표시 문제 디버깅

## 현재 상황

**백엔드 로그 (성공):**
```
1005: 상담원 대시보드로 브로드캐스트 - 대상: 1개  ✅
1006: 상담원 리포트 자동 생성 완료  ✅
```

**프론트엔드 화면:**
- 왼쪽: 리포트 카드 표시됨 ("세션 3h1zgmj4") ✅
- 오른쪽: 상세 정보 비어있음 ❌
  - "요약 정보가 없습니다."

## 🔍 진단 단계

### 1단계: 브라우저 콘솔 확인 ⭐ (가장 중요!)

```
F12 → 콘솔 탭
```

**확인할 로그:**
```javascript
✅ 정상 작동 시:
📩 상담원 대시보드 메시지 수신: {...}
✅ handover_report 타입 확인됨
📦 데이터: { status: "success", customer_sentiment: "NEUTRAL", ... }
📝 생성된 리포트: { ... }
📊 업데이트된 리포트 목록: 1 개

❌ 문제가 있을 시:
❌ message.data가 없습니다!
❌ 메시지 파싱 오류: ...
```

### 2단계: 네트워크 탭 확인

```
F12 → Network 탭 → WS 필터
→ consultant_dashboard 클릭
→ Messages 탭
→ 수신된 메시지 확인
```

**확인할 내용:**
```json
{
  "type": "handover_report",
  "session_id": "sess_...",
  "data": {
    "status": "success",
    "customer_sentiment": "NEUTRAL",
    "summary": "...",
    "extracted_keywords": [...],
    "kms_recommendations": [...]
  }
}
```

### 3단계: 하드 리프레시

브라우저 캐시 문제일 수 있습니다:

```
Ctrl + Shift + R (강력 새로고침)
```

또는:

```
Ctrl + Shift + N (시크릿 모드)
→ http://localhost:5173/consultant
```

---

## 📸 스크린샷 요청

다음 스크린샷을 공유해주세요:

1. **브라우저 콘솔 (F12)** - 전체 로그
2. **Network → WS → Messages** - 수신된 WebSocket 메시지

---

## 🔧 임시 디버깅 코드

브라우저 콘솔에서 직접 실행:

```javascript
// 현재 WebSocket 연결 상태 확인
console.log('WebSocket 상태:', ws?.readyState);
// 1 = OPEN, 3 = CLOSED

// 수동으로 테스트 메시지 처리
const testMessage = {
  type: 'handover_report',
  session_id: 'test_session_123',
  data: {
    status: 'success',
    customer_sentiment: 'POSITIVE',
    summary: '테스트 고객이 카드 분실 문의를 하였습니다.',
    extracted_keywords: ['카드분실', '긴급'],
    kms_recommendations: [
      {
        title: '카드 분실 신고 방법',
        url: 'http://example.com',
        relevance_score: 0.95
      }
    ]
  }
};

// 메시지 이벤트 시뮬레이션
const event = new MessageEvent('message', {
  data: JSON.stringify(testMessage)
});

// 현재 WebSocket의 onmessage 핸들러 호출
if (ws && ws.onmessage) {
  ws.onmessage(event);
}
```

---

## 🚀 빠른 해결책

### 해결책 1: 강력 새로고침

```
1. 상담원 대시보드 페이지에서
2. Ctrl + Shift + R
3. 다시 채팅에서 이관 요청
```

### 해결책 2: 캐시 완전 삭제

```
F12 → Application 탭 → Storage → Clear site data
또는
설정 → 인터넷 사용 기록 삭제 → 캐시된 이미지 및 파일
```

### 해결책 3: 시크릿 모드

```
Ctrl + Shift + N
→ http://localhost:5173/consultant
→ 새 탭: http://localhost:5173
→ 이관 요청
```

---

## 🔍 확인할 파일

### 백엔드 (`app/api/v1/chat.py`)

데이터 전송 부분:
```python
report_data = {
    "type": "handover_report",
    "session_id": session_id,
    "data": {
        "status": handover_response.status,
        "customer_sentiment": handover_response.analysis_result.customer_sentiment.value,
        "summary": handover_response.analysis_result.summary,
        "extracted_keywords": handover_response.analysis_result.extracted_keywords,
        "kms_recommendations": [...]
    }
}
```

### 프론트엔드 (`frontend/src/pages/ConsultantDashboard.tsx`)

데이터 수신 부분:
```typescript
const newReport: HandoverReportWithTimestamp = {
    status: message.data.status || 'success',
    analysis_result: {
        customer_sentiment: message.data.customer_sentiment || 'NEUTRAL',
        summary: message.data.summary || '요약 정보 없음',
        extracted_keywords: message.data.extracted_keywords || [],
        kms_recommendations: message.data.kms_recommendations || []
    },
    session_id: message.session_id || `sess_${Date.now()}`,
    timestamp: new Date(),
    processing_status: 'pending'
};
```

---

## 💡 가능한 문제

1. **브라우저 캐시**
   - 오래된 JavaScript 파일 실행 중
   - 해결: 강력 새로고침 (Ctrl + Shift + R)

2. **데이터 구조 불일치**
   - 백엔드와 프론트엔드 간 데이터 형식 차이
   - 해결: 콘솔 로그로 실제 데이터 확인

3. **WebSocket 연결 문제**
   - 연결은 되었지만 메시지 수신 실패
   - 해결: 네트워크 탭에서 확인

4. **React State 업데이트 문제**
   - 데이터는 받았지만 화면 렌더링 안 됨
   - 해결: React DevTools 확인

---

## ⚡ 다음 단계

1. **F12 → 콘솔 탭 스크린샷 공유**
2. **Network → WS → Messages 스크린샷 공유**

이 두 가지만 확인하면 정확한 원인을 파악할 수 있습니다!

