# Voice Chatbot (음성 보이스봇)

Bank AICC 프로젝트의 음성 기반 고객 상담 보이스봇 프론트엔드입니다.

## 실행 방법

### 1. 의존성 설치
```bash
cd voice-chatbot
npm install
```

### 2. 개발 서버 실행
```bash
npm start
```
[http://localhost:3002](http://localhost:3002)에서 확인할 수 있습니다.

### 3. 백엔드 서버
백엔드 서버가 `http://localhost:8000`에서 실행 중이어야 합니다.

## 주요 기능

- 음성 녹음 및 STT (Speech-to-Text) 변환
- AI 응답 및 TTS (Text-to-Speech) 재생
- 실시간 대화 표시
- 상담원 연결 요청

## 기술 스택

- React 19 + TypeScript
- Vite
- Axios
- Web Audio API (MediaRecorder)

## 폴더 구조

```
src/
├── components/
│   ├── VoiceButton.tsx    # 마이크 버튼 컴포넌트
│   ├── VoiceButton.css
│   ├── ChatMessage.tsx    # 메시지 컴포넌트
│   └── ChatMessage.css
├── hooks/
│   └── useAudioRecorder.ts # 마이크 녹음 훅
├── services/
│   └── api.ts             # Voice API 연동
├── App.tsx
├── App.css
└── main.tsx
```

## API 연동

- `POST /api/v1/voice/message` - 음성 메시지 전송 (STT → AI → TTS)
- `POST /api/v1/handover/request` - 상담원 이관 요청
