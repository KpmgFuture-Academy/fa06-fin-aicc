# 🚀 WebSocket & Nginx 빠른 시작 가이드

Bank AICC 프로젝트에 WebSocket 양방향 통신과 Nginx Reverse Proxy가 추가되었습니다!

## ✨ 새로운 기능

- ✅ **WebSocket 실시간 통신**: 양방향 메시지 송수신
- ✅ **자동 재연결**: 연결 끊김 시 자동 복구
- ✅ **HTTP Fallback**: WebSocket 실패 시 HTTP로 자동 전환
- ✅ **Nginx Reverse Proxy**: 보안, 성능, 로드 밸런싱
- ✅ **기존 API 호환**: HTTP REST API 그대로 유지

## 📦 필요한 패키지

모든 필요한 패키지는 이미 설치되어 있습니다:
- FastAPI (WebSocket 기본 지원)
- uvicorn[standard] (WebSocket 지원)
- Nginx (Docker 이미지)

추가 설치 불필요! ✨

## 🎯 실행 방법

### 방법 1: Docker Compose (권장)

```bash
# 1. 환경 변수 설정 (.env 파일 확인)
cp .env.example .env  # .env.example이 없으면 생략
# .env 파일에서 OPENAI_API_KEY 등 설정

# 2. Docker Compose 실행
docker-compose up -d --build

# 3. 로그 확인
docker-compose logs -f

# 4. 브라우저에서 접속
# http://localhost
```

### 방법 2: 개발 환경 (Docker 없이)

```bash
# 터미널 1: 백엔드
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 터미널 2: 프론트엔드
cd frontend
npm run dev

# 터미널 3: Nginx (선택사항)
# nginx.conf 설정 후
nginx -c $(pwd)/nginx.conf
```

## 🧪 테스트

### 1. 헬스체크

```bash
# Docker 환경
curl http://localhost/health

# 개발 환경
curl http://localhost:8000/health
```

### 2. HTTP API 테스트

```bash
curl -X POST http://localhost/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_001",
    "user_message": "안녕하세요"
  }'
```

### 3. WebSocket 테스트

```bash
# Python 스크립트 사용
pip install websockets

# 기본 테스트
python test_websocket.py

# 커스텀 메시지
python test_websocket.py test_001 "대출 금리가 얼마인가요?"

# Docker 환경 (Nginx 통과)
python test_websocket.py test_001 "안녕하세요" ws://localhost

# 연속 메시지 테스트
python test_websocket.py --multi test_001
```

### 4. 브라우저 테스트

1. http://localhost 접속
2. 우측 하단에서 연결 상태 확인:
   - 🟢 **WebSocket 연결**: 실시간 통신 활성화
   - 🔴 **연결 끊김**: HTTP fallback 모드
3. 채팅 메시지 전송
4. 개발자 도구 콘솔에서 로그 확인

## 📊 연결 상태 확인

프론트엔드 UI 우측 하단에 실시간 연결 상태가 표시됩니다:

| 상태 | 의미 |
|------|------|
| 🟢 WebSocket 연결 | WebSocket으로 실시간 통신 중 |
| 🟡 연결 중... | WebSocket 연결 시도 중 |
| 🔴 연결 끊김 | WebSocket 연결 끊김 (재연결 시도 중) |
| 🔵 HTTP 모드 | HTTP API 사용 중 (fallback) |

## 🔍 주요 엔드포인트

### HTTP API (기존 유지)

- `POST /api/v1/chat/message` - 채팅 메시지 (HTTP)
- `POST /api/v1/handover/analyze` - 상담원 이관
- `GET /health` - 헬스체크

### WebSocket (신규)

- `ws://localhost/api/v1/chat/ws/{session_id}` - WebSocket 연결

### Nginx 모니터링

- `GET /nginx_status` - Nginx 상태 (로컬에서만 접근 가능)

## 🐛 문제 해결

### WebSocket 연결 안 됨

```bash
# 백엔드 서버 확인
curl http://localhost/health

# Docker 컨테이너 확인
docker-compose ps
docker-compose logs backend
docker-compose logs nginx

# 포트 확인
netstat -an | grep 8000  # 백엔드
netstat -an | grep 80    # Nginx
```

### HTTP는 되는데 WebSocket이 안 됨

1. Nginx 설정 확인:
   ```bash
   docker-compose exec nginx cat /etc/nginx/nginx.conf | grep ws
   ```

2. WebSocket 업그레이드 헤더 확인:
   ```nginx
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```

3. Nginx 재시작:
   ```bash
   docker-compose restart nginx
   ```

### 502 Bad Gateway

백엔드 컨테이너가 실행 중인지 확인:
```bash
docker-compose ps
docker-compose up -d backend
```

## 📚 상세 문서

더 자세한 내용은 다음 문서를 참고하세요:

- [WebSocket & Nginx 가이드](docs/WEBSOCKET_NGINX_GUIDE.md) - 전체 가이드
- [아키텍처 분석](ARCHITECTURE_ANALYSIS.md) - 시스템 구조
- [디버깅 가이드](docs/DEBUGGING.md) - 문제 해결

## 🎉 완료!

이제 실시간 양방향 통신이 가능한 채팅 시스템을 사용할 수 있습니다!

질문이나 문제가 있으면 이슈를 등록해 주세요.

