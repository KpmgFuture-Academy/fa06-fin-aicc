# 디버깅 가이드

## 프론트엔드에서 백엔드로 요청이 가지 않는 경우

### 1. 브라우저 개발자 도구 확인

1. 브라우저에서 `F12` 키를 눌러 개발자 도구 열기
2. `Network` 탭 확인
3. 채팅 메시지 전송 시 요청이 보이는지 확인
4. 요청 URL 확인:
   - 정상: `http://localhost:8000/api/v1/chat/message`
   - 프록시 사용: `http://localhost:3000/api/v1/chat/message`

### 2. 백엔드 서버 실행 확인

백엔드 서버가 실행 중인지 확인:

```powershell
# 새 터미널에서
curl http://localhost:8000/health
```

또는 브라우저에서 직접 접속:
- `http://localhost:8000/health`
- `http://localhost:8000/docs`

### 3. 프론트엔드 콘솔 확인

브라우저 콘솔(`F12` → `Console`)에서 에러 메시지 확인:
- `Network Error`: 백엔드 서버에 연결할 수 없음
- `404 Not Found`: API 경로가 잘못됨
- `CORS Error`: CORS 설정 문제

### 4. API 연결 방식 확인

현재 설정:
- **직접 연결**: `http://localhost:8000` (기본값)
- **프록시 사용**: 환경 변수로 변경 가능

프록시를 사용하려면:
1. 프론트엔드 `.env` 파일에 `VITE_API_BASE_URL=` (빈 값)
2. `vite.config.ts`의 프록시 설정 확인

### 5. 네트워크 요청 확인

브라우저 개발자 도구 → Network 탭에서:
- 요청이 전송되는지 확인
- 요청 URL 확인
- 응답 상태 코드 확인
- 응답 본문 확인

### 6. 백엔드 로그 확인

백엔드 서버 터미널에서:
- 요청이 들어오는지 확인
- 에러 로그 확인

### 7. 포트 확인

- **백엔드**: `http://localhost:8000`
- **프론트엔드**: `http://localhost:3000`

포트가 다른 경우 `.env` 파일에서 수정

