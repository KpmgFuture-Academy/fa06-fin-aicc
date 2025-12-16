# WebSocket 채팅 메시지가 HTTP로 전송되는 문제 해결

## 🔍 현재 상태

### ✅ 정상 동작
- WebSocket 연결 성공
- Ping/Pong 메시지는 WebSocket으로 정상 전송

### ❌ 문제
- **채팅 메시지가 HTTP API로 전송됨**
- WebSocket으로 전송되어야 함

---

## 🛠️ 해결 단계

### 1단계: 브라우저 캐시 완전 삭제 ⭐ (가장 중요!)

#### Windows (Chrome/Edge):
```
1. F12 키를 눌러 개발자 도구 열기
2. 네트워크 탭 클릭
3. 페이지에서 마우스 오른쪽 버튼 → "Empty Cache and Hard Reload" (캐시 비우기 및 강력 새로고침)

또는

Ctrl + Shift + Delete → 캐시된 이미지 및 파일 선택 → 삭제
```

#### 시크릿 모드 테스트:
```
Ctrl + Shift + N (Chrome)
Ctrl + Shift + P (Edge/Firefox)

→ 시크릿 창에서 http://localhost:5173 접속
```

---

### 2단계: Vite 캐시 삭제

PowerShell에서 실행:
```powershell
# 프론트엔드 디렉토리로 이동
cd frontend

# Vite 캐시 삭제
Remove-Item -Recurse -Force node_modules\.vite -ErrorAction SilentlyContinue

# 빌드 캐시 삭제 (있다면)
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue

# 프론트엔드 재시작
npm run dev
```

---

### 3단계: 브라우저 콘솔 로그 확인

F12 → 콘솔 탭에서 다음 로그 확인:

#### ✅ 정상적인 경우:
```
✅ WebSocket 모드 활성화
WebSocket으로 메시지 전송: { session_id: "...", user_message: "..." }
```

#### ❌ 문제가 있는 경우:
```
HTTP API 호출 시작: { reason: "WebSocket 비활성화" }
또는
HTTP API 호출 시작: { reason: "WebSocket 연결 끊김" }
```

---

### 4단계: 프론트엔드 코드 확인

`frontend/src/App.tsx`의 54-57번 줄이 제대로 실행되는지 확인:

```typescript
// 연결 성공 시
if (status === 'connected') {
  setUseWebSocket(true);
  console.log('✅ WebSocket 모드 활성화'); // ← 이 로그가 출력되는지 확인
}
```

---

## 🧪 테스트 방법

### 1. 백엔드 로그 확인
```
2025-12-06 HH:MM:SS - app.api.v1.chat - INFO - WebSocket 메시지 수신 - 세션: sess_xxx, 타입: message
2025-12-06 HH:MM:SS - app.api.v1.chat - INFO - WebSocket 메시지 전송 완료 - 세션: sess_xxx, 타입: response
```

✅ **위 로그가 보이면 성공!**  
❌ `POST /api/v1/chat/message`가 보이면 여전히 HTTP 사용 중

### 2. 프론트엔드 콘솔 로그 확인
```
✅ WebSocket 모드 활성화
WebSocket으로 메시지 전송: { ... }
WebSocket 메시지 수신: { type: "response", data: { ... } }
```

---

## 📋 체크리스트

- [ ] 브라우저 강력 새로고침 (Ctrl + Shift + R)
- [ ] 시크릿 모드에서 테스트
- [ ] Vite 캐시 삭제 (`node_modules/.vite`)
- [ ] 프론트엔드 재시작 (`npm run dev`)
- [ ] 브라우저 콘솔에서 "✅ WebSocket 모드 활성화" 로그 확인
- [ ] 백엔드 로그에서 "WebSocket 메시지 수신 - 타입: message" 확인

---

## 🚨 여전히 문제가 있다면

다음 정보를 공유해주세요:

1. **브라우저 콘솔 로그 (전체)**
   - F12 → 콘솔 탭 스크린샷
   
2. **백엔드 로그 (메시지 전송 시점)**
   - 메시지 입력 후 나타나는 로그

3. **네트워크 탭**
   - F12 → 네트워크 탭
   - WS (WebSocket) 필터 선택
   - 연결 상태 확인

