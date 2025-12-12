# Network Error 해결 가이드

## 문제: "Network Error" 발생

프론트엔드에서 백엔드 API로 요청을 보낼 때 "Network Error"가 발생하는 경우의 해결 방법입니다.

## 원인 확인

### 1. 백엔드 서버 실행 확인

가장 먼저 백엔드 서버가 실행 중인지 확인하세요:

```powershell
# 백엔드 서버 실행 확인
# 터미널에서 다음 명령어로 확인
curl http://localhost:8000/health
```

또는 브라우저에서 직접 접속:
- `http://localhost:8000/health`
- `http://localhost:8000/docs` (Swagger UI)

### 2. 포트 확인

- **백엔드**: `http://localhost:8000`
- **프론트엔드**: `http://localhost:3000`

### 3. 프록시 설정 확인

Vite 프록시 설정이 올바른지 확인:
- `frontend/vite.config.ts`에서 `/api` 경로가 `http://localhost:8000`으로 프록시되도록 설정되어 있는지 확인

## 해결 방법

### 방법 1: 백엔드 서버 실행

백엔드 서버가 실행되지 않은 경우:

```powershell
# 프로젝트 루트에서
cd c:\Users\Admin\aicc\fa06-fin-aicc
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 정상적으로 시작되면:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 방법 2: 프론트엔드 재시작

프론트엔드 서버를 재시작하세요:

```powershell
# 프론트엔드 폴더에서
cd frontend
npm run dev
```

### 방법 3: 브라우저 개발자 도구 확인

1. 브라우저에서 `F12` 키를 눌러 개발자 도구 열기
2. `Network` 탭 확인
3. 요청이 실패하는 경우:
   - 요청 URL 확인
   - 상태 코드 확인 (404, 500 등)
   - 에러 메시지 확인

### 방법 4: 직접 API 테스트

브라우저에서 직접 API를 테스트:

```javascript
// 브라우저 콘솔에서 실행
fetch('http://localhost:8000/api/v1/chat/message', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    session_id: 'test_session',
    user_message: '테스트 메시지'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 방법 5: CORS 문제 확인

백엔드의 CORS 설정이 올바른지 확인:
- `app/main.py`에서 `allow_origins=["*"]`로 설정되어 있는지 확인

### 방법 6: 방화벽 확인

Windows 방화벽이 포트 8000을 차단하지 않는지 확인:

```powershell
# 방화벽 규칙 확인
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*python*" -or $_.DisplayName -like "*uvicorn*"}
```

## 체크리스트

- [ ] 백엔드 서버가 `http://localhost:8000`에서 실행 중인가?
- [ ] 프론트엔드 서버가 `http://localhost:3000`에서 실행 중인가?
- [ ] 브라우저에서 `http://localhost:8000/health`에 접속할 수 있는가?
- [ ] 브라우저 개발자 도구의 Network 탭에서 요청이 보이는가?
- [ ] 요청 URL이 올바른가? (`/api/v1/chat/message`)
- [ ] CORS 오류가 발생하지 않는가?

## 일반적인 해결 순서

1. **백엔드 서버 실행 확인**
   ```powershell
   # 새 터미널에서
   cd c:\Users\Admin\aicc\fa06-fin-aicc
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **프론트엔드 서버 재시작**
   ```powershell
   # 다른 터미널에서
   cd frontend
   npm run dev
   ```

3. **브라우저 새로고침**
   - `Ctrl + F5` (강력 새로고침)

4. **브라우저 개발자 도구 확인**
   - `F12` → `Network` 탭
   - 요청이 실패하는 경우 에러 메시지 확인

## 추가 디버깅

### 백엔드 로그 확인

백엔드 서버 터미널에서 다음 로그가 표시되는지 확인:
```
INFO:     "POST /api/v1/chat/message HTTP/1.1" 200 OK
```

### 프론트엔드 콘솔 확인

브라우저 콘솔(`F12` → `Console`)에서 에러 메시지 확인

### 네트워크 요청 확인

브라우저 개발자 도구 → Network 탭에서:
- 요청이 전송되는지 확인
- 응답 상태 코드 확인
- 응답 본문 확인

