# WebSocket & Nginx Reverse Proxy 가이드

이 문서는 Bank AICC 프로젝트의 WebSocket 양방향 통신과 Nginx Reverse Proxy 설정에 대한 가이드입니다.

## 📋 목차

1. [개요](#개요)
2. [WebSocket 구현](#websocket-구현)
3. [Nginx 설정](#nginx-설정)
4. [실행 방법](#실행-방법)
5. [테스트](#테스트)
6. [트러블슈팅](#트러블슈팅)

---

## 개요

### 아키텍처

```
클라이언트 (브라우저)
    ↕ HTTP/WebSocket
Nginx Reverse Proxy (포트 80)
    ↕ HTTP/WebSocket
FastAPI 백엔드 (포트 8000)
    ↕
MySQL 데이터베이스 (포트 3306)
```

### 주요 특징

- **WebSocket 우선, HTTP Fallback**: 실시간 통신을 위해 WebSocket을 우선 사용하고, 연결 실패 시 HTTP로 자동 전환
- **Nginx Reverse Proxy**: 보안, 로드 밸런싱, SSL/TLS 종료, 정적 파일 캐싱
- **기존 HTTP API 유지**: 기존 REST API는 그대로 유지되어 호환성 보장

---

## WebSocket 구현

### 백엔드 (FastAPI)

#### WebSocket 엔드포인트

```python
# app/api/v1/chat.py

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "message":
                # 워크플로우 실행
                response = await process_chat_message(request)
                
                # 응답 전송
                await manager.send_message(session_id, {
                    "type": "response",
                    "data": response
                })
    
    except WebSocketDisconnect:
        manager.disconnect(session_id)
```

#### 메시지 포맷

**클라이언트 → 서버**:
```json
{
  "type": "message",
  "user_message": "대출 금리 얼마인가요?"
}
```

**서버 → 클라이언트**:
```json
{
  "type": "response",
  "data": {
    "ai_message": "대출 금리는...",
    "intent": "INFO_REQ",
    "suggested_action": "CONTINUE",
    "source_documents": [...]
  }
}
```

### 프론트엔드 (React + TypeScript)

#### WebSocket 서비스

```typescript
// frontend/src/services/websocket.ts

export class WebSocketService {
  connect(sessionId: string): Promise<void> {
    const wsUrl = `ws://localhost/api/v1/chat/ws/${sessionId}`;
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('WebSocket 연결 성공');
      this.startPingInterval();  // 연결 유지
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };
  }
}
```

#### 자동 재연결

WebSocket 연결이 끊어지면 자동으로 재연결을 시도합니다 (최대 5회).

```typescript
private attemptReconnect(): void {
  this.reconnectAttempts++;
  setTimeout(() => {
    if (this.sessionId) {
      this.connect(this.sessionId);
    }
  }, this.reconnectDelay * this.reconnectAttempts);
}
```

---

## Nginx 설정

### 주요 설정

#### 1. WebSocket 프록시

```nginx
location /api/v1/chat/ws/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    
    # WebSocket 업그레이드 필수 헤더
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    
    # 장시간 연결 유지
    proxy_read_timeout 7d;
    proxy_send_timeout 7d;
}
```

#### 2. HTTP API 프록시

```nginx
location /api/ {
    proxy_pass http://backend;
    
    # LLM 응답 대기를 위한 긴 타임아웃
    proxy_read_timeout 300s;  # 5분
    
    # 스트리밍 응답을 위해 버퍼링 비활성화
    proxy_buffering off;
}
```

#### 3. Rate Limiting (DDoS 방어)

```nginx
# 초당 10개 요청 제한
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
}
```

#### 4. Gzip 압축

```nginx
gzip on;
gzip_types text/plain application/json application/javascript;
gzip_min_length 1024;
```

---

## 실행 방법

### 개발 환경 (Docker 없이)

#### 1. 백엔드 실행

```bash
# 가상 환경 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

#### 3. 접속

- **백엔드**: http://localhost:8000
- **프론트엔드**: http://localhost:5173
- **WebSocket**: ws://localhost:8000/api/v1/chat/ws/{session_id}

### Docker Compose (Nginx 포함)

#### 1. 환경 변수 설정

`.env` 파일을 생성하고 필요한 값을 설정합니다:

```bash
MYSQL_ROOT_PASSWORD=password
OPENAI_API_KEY=sk-your-api-key-here
```

#### 2. Docker Compose 실행

```bash
# 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 상태 확인
docker-compose ps
```

#### 3. 접속

- **모든 서비스**: http://localhost (Nginx를 통해)
- **프론트엔드**: http://localhost/
- **백엔드 API**: http://localhost/api/
- **WebSocket**: ws://localhost/api/v1/chat/ws/{session_id}
- **헬스체크**: http://localhost/health

#### 4. 종료

```bash
docker-compose down

# 볼륨까지 삭제 (DB 데이터 포함)
docker-compose down -v
```

---

## 테스트

### 1. HTTP API 테스트

```bash
# 헬스체크
curl http://localhost/health

# 채팅 메시지 (HTTP)
curl -X POST http://localhost/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "user_message": "대출 금리가 얼마인가요?"
  }'
```

### 2. WebSocket 테스트 (Python)

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost/api/v1/chat/ws/test_session_001"
    
    async with websockets.connect(uri) as websocket:
        # 연결 상태 메시지 수신
        status = await websocket.recv()
        print(f"Status: {status}")
        
        # 메시지 전송
        await websocket.send(json.dumps({
            "type": "message",
            "user_message": "대출 금리가 얼마인가요?"
        }))
        
        # 응답 수신
        response = await websocket.recv()
        print(f"Response: {response}")

asyncio.run(test_websocket())
```

### 3. 브라우저 콘솔 테스트

```javascript
const ws = new WebSocket('ws://localhost/api/v1/chat/ws/test_session_001');

ws.onopen = () => {
  console.log('WebSocket 연결 성공');
  
  // 메시지 전송
  ws.send(JSON.stringify({
    type: 'message',
    user_message: '대출 금리가 얼마인가요?'
  }));
};

ws.onmessage = (event) => {
  console.log('메시지 수신:', JSON.parse(event.data));
};

ws.onerror = (error) => {
  console.error('WebSocket 오류:', error);
};
```

### 4. 연결 상태 확인

프론트엔드 UI 우측 하단에서 연결 상태를 확인할 수 있습니다:

- 🟢 **WebSocket 연결**: 실시간 통신 활성화
- 🟡 **연결 중...**: WebSocket 연결 시도 중
- 🔴 **연결 끊김**: WebSocket 연결 끊김 (HTTP fallback)
- 🔵 **HTTP 모드**: HTTP API 사용 중

---

## 트러블슈팅

### WebSocket 연결 실패

#### 증상
- 프론트엔드에서 "WebSocket 연결 오류" 메시지
- 연결 상태가 계속 "연결 중..."

#### 해결 방법

1. **백엔드 서버 확인**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Nginx 설정 확인**
   ```bash
   docker-compose logs nginx
   ```

3. **방화벽 확인**
   - 80 포트와 8000 포트가 열려있는지 확인

4. **WebSocket URL 확인**
   - 개발 환경: `ws://localhost:8000/api/v1/chat/ws/{session_id}`
   - Docker 환경: `ws://localhost/api/v1/chat/ws/{session_id}`

### Nginx 502 Bad Gateway

#### 증상
- Nginx가 백엔드에 연결할 수 없음

#### 해결 방법

1. **백엔드 컨테이너 확인**
   ```bash
   docker-compose ps
   docker-compose logs backend
   ```

2. **네트워크 확인**
   ```bash
   docker network inspect aicc-network
   ```

3. **upstream 설정 확인** (nginx.conf)
   ```nginx
   upstream backend {
       server backend:8000;  # 컨테이너 이름이 정확한지 확인
   }
   ```

### CORS 오류

#### 증상
- 브라우저 콘솔에 CORS 오류 메시지

#### 해결 방법

Nginx를 사용하면 프론트엔드와 백엔드가 같은 도메인을 공유하므로 CORS 문제가 발생하지 않습니다.

만약 CORS 오류가 발생한다면:

1. **Nginx 헤더 추가** (nginx.conf)
   ```nginx
   add_header Access-Control-Allow-Origin "*" always;
   add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
   add_header Access-Control-Allow-Headers "Content-Type" always;
   ```

2. **백엔드 CORS 설정 확인** (app/main.py)
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

### LLM 응답 타임아웃

#### 증상
- 504 Gateway Timeout 오류

#### 해결 방법

1. **Nginx 타임아웃 증가** (nginx.conf)
   ```nginx
   location /api/ {
       proxy_read_timeout 600s;  # 10분으로 증가
   }
   ```

2. **FastAPI 타임아웃 설정**
   ```python
   # app/core/config.py
   llm_timeout: int = 300  # 5분
   ```

3. **프론트엔드 타임아웃 설정**
   ```bash
   # .env
   VITE_API_TIMEOUT=600000  # 10분 (밀리초)
   ```

---

## 성능 모니터링

### Nginx 상태 확인

```bash
# Nginx 상태 페이지 (로컬에서만 접근 가능)
curl http://localhost/nginx_status
```

출력 예시:
```
Active connections: 3
server accepts handled requests
 10 10 25
Reading: 0 Writing: 1 Waiting: 2
```

### 로그 확인

```bash
# Nginx 액세스 로그
docker-compose logs nginx | grep access

# 백엔드 로그
docker-compose logs backend

# 실시간 로그
docker-compose logs -f
```

---

## 프로덕션 배포

### HTTPS 설정 (Let's Encrypt)

1. **Certbot 설치 및 인증서 발급**
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```

2. **nginx.conf 주석 해제**
   ```nginx
   server {
       listen 443 ssl http2;
       server_name yourdomain.com;
       
       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
   }
   ```

3. **자동 갱신 설정**
   ```bash
   sudo certbot renew --dry-run
   ```

### 환경 변수 설정

프로덕션 환경에서는 `.env` 파일에 실제 값을 설정합니다:

```bash
MYSQL_ROOT_PASSWORD=<strong-password>
OPENAI_API_KEY=<real-api-key>
VITE_API_BASE_URL=https://yourdomain.com/api
VITE_WS_URL=wss://yourdomain.com/api/v1/chat/ws
```

---

## 참고 자료

- [FastAPI WebSocket 문서](https://fastapi.tiangolo.com/advanced/websockets/)
- [Nginx WebSocket 프록시](https://nginx.org/en/docs/http/websocket.html)
- [MDN WebSocket API](https://developer.mozilla.org/ko/docs/Web/API/WebSocket)

