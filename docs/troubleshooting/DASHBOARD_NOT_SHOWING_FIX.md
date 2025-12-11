# 🔧 상담원 대시보드에 리포트가 표시되지 않는 문제 해결

## 🐛 문제 원인

로그 분석 결과:

```python
# 16:09:23 - 리포트 생성
1000: 상담원 대시보드로 브로드캐스트 - 대상: 0개  ← 대시보드 연결 없음!
1001: 상담원 리포트 자동 생성 완료

# 16:09:30 - 대시보드 연결 (7초 후)
1004: WebSocket 연결 수립 - 세션: consultant_dashboard  ← 늦게 연결됨
```

**핵심 문제**: 리포트가 생성될 때 상담원 대시보드가 연결되어 있지 않았습니다!

---

## ✅ 해결 방법 (2가지)

### 방법 1: 연결 순서 변경 ⭐ (즉시 테스트)

**올바른 순서:**
1. **먼저** 상담원 대시보드 열기
   ```
   http://localhost:5173/consultant
   ```

2. **그 다음** 채팅창 열기 (새 탭)
   ```
   http://localhost:5173
   ```

3. **채팅창에서** 이관 요청
   ```
   "상담원 연결해주세요"
   → "네"
   → "홍길동"
   → "카드 분실"
   → "어제 카드를 잃어버렸어요"
   ```

4. **대시보드에서** 실시간 수신 확인

---

### 방법 2: 백엔드 캐싱 (영구 해결) ✨

**이미 수정 완료!**

`app/api/v1/chat.py`에 다음 기능 추가:
1. **리포트 캐싱**: 생성된 리포트를 메모리에 저장 (최대 50개)
2. **연결 시 전송**: 상담원 대시보드 연결 시 캐시된 리포트 자동 전송

**이제 순서와 상관없이 작동합니다!**

---

## 🧪 테스트 방법

### 테스트 1: HTML 직접 테스트

`test_consultant_dashboard_websocket.html` 파일을 브라우저에서 열기:

```
파일 탐색기에서:
C:\Users\Admin\aicc\fa06-fin-aicc\test_consultant_dashboard_websocket.html

마우스 오른쪽 클릭 → "연결 프로그램" → "Chrome" 또는 "Edge"
```

**"연결 시작" 버튼 클릭 후:**

✅ **성공 시:**
```
✅ WebSocket 연결 성공!
ℹ️ 상태 메시지: connected
📩 메시지 수신: type=handover_report  (이미 생성된 리포트가 있다면)
✅ handover_report 수신!
📦 리포트 데이터: { ... }
```

❌ **실패 시:**
```
❌ WebSocket 오류 발생
🔌 WebSocket 연결 종료: code=1006
```
→ 백엔드가 실행 중인지 확인!

---

### 테스트 2: 실제 대시보드 테스트

#### 1단계: 브라우저 캐시 완전 삭제

```
F12 → 새로고침 버튼 우클릭 → "캐시 비우기 및 강력 새로고침"
```

또는 **시크릿 모드**:
```
Ctrl + Shift + N
→ http://localhost:5173/consultant
```

#### 2단계: 브라우저 콘솔 확인

```
F12 → 콘솔 탭
```

다음 로그를 찾아보세요:
```
✅ WebSocket 연결 성공
📩 상담원 대시보드 메시지 수신: { type: "status", message: "connected" }
📩 상담원 대시보드 메시지 수신: { type: "handover_report", ... }
✅ handover_report 타입 확인됨
📝 생성된 리포트: { ... }
📊 업데이트된 리포트 목록: 1 개
```

❌ **아무 로그가 없다면**:
- JavaScript가 로드되지 않음 (캐시 문제)
- 시크릿 모드에서 재테스트

---

## 🔍 디버깅 체크리스트

### 1. 백엔드 확인 ✅

터미널에서 다음 로그 확인:

```
✅ WebSocket 연결 수립 - 세션: consultant_dashboard
✅ 상담원 대시보드에 최근 리포트 전송 - 리포트 수: X
```

### 2. 프론트엔드 콘솔 확인 (F12)

```javascript
// 콘솔에서 직접 실행해서 테스트
const ws = new WebSocket('ws://localhost:8000/api/v1/chat/ws/consultant_dashboard');

ws.onopen = () => console.log('✅ 연결 성공');
ws.onmessage = (e) => console.log('📩 메시지:', JSON.parse(e.data));
ws.onerror = (e) => console.error('❌ 오류:', e);
```

### 3. 네트워크 탭 확인 (F12)

```
F12 → Network 탭 → WS 필터
→ consultant_dashboard 연결 확인
→ Messages 탭에서 수신 메시지 확인
```

---

## 🚨 여전히 문제가 있다면

### 확인 1: 리포트가 생성되었는지

채팅에서 전체 플로우 완료:
```
1. "상담원 연결해주세요"
2. "네" (동의)
3. "홍길동" (이름)
4. "카드 분실" (문의 유형)
5. "어제 카드를 잃어버렸어요" (상세 내용)
```

백엔드 로그에서 확인:
```
✅ 정보 수집 완료 - 수집된 정보: {...}
✅ 워크플로우 완료 - action: ActionType.HANDOVER
✅ 상담원 이관 감지 (정보 수집 완료) - 자동 리포트 생성 시작
✅ 상담원 대시보드로 브로드캐스트 - 대상: X개
```

### 확인 2: 대시보드가 제대로 연결되었는지

브라우저 콘솔 (F12) 에서:
```javascript
console.log('연결 상태:', websocketService?.ws?.readyState);
// 1이면 OPEN (정상)
// 3이면 CLOSED (문제)
```

### 확인 3: 프론트엔드 코드 문제

브라우저 콘솔에서:
```javascript
// 수동으로 테스트 메시지 처리
const testMessage = {
  type: 'handover_report',
  session_id: 'test_123',
  data: {
    status: 'success',
    customer_sentiment: 'POSITIVE',
    summary: '테스트 요약',
    extracted_keywords: ['테스트'],
    kms_recommendations: []
  }
};

// 이 메시지를 콘솔에 출력
console.log('테스트 메시지:', testMessage);
```

---

## 📸 필요한 스크린샷

문제가 지속되면 다음을 공유해주세요:

1. **브라우저 콘솔 (F12)** - 전체 로그
2. **네트워크 탭 (F12 → Network → WS)** - WebSocket 메시지
3. **백엔드 로그** - "브로드캐스트 - 대상: X개" 부분

---

## 💡 빠른 테스트

HTML 테스트 파일 실행:
```
test_consultant_dashboard_websocket.html 파일을 브라우저에서 열기
→ "연결 시작" 버튼 클릭
→ 로그 확인
```

이 파일은 순수 JavaScript로만 작동하므로 React/Vite 캐시 문제를 배제하고 테스트할 수 있습니다!

