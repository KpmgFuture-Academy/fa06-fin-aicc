# Voice Chatbot Revision (음성 보이스봇)

Bank AICC 프로젝트의 음성 기반 고객 상담 보이스봇 프론트엔드입니다.

## 실행 방법

### 1. 의존성 설치
```bash
cd voice-chatbot-revision
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

### 실시간 음성 스트리밍
- **양방향 WebSocket 스트리밍**: STT + AI 응답 + TTS를 단일 연결로 처리
- **실시간 STT**: VITO API를 통한 실시간 음성 인식

### VAD (Voice Activity Detection)
- **2초 침묵 감지**: 사용자가 말을 멈추면 자동으로 전송
- **RMS 기반 볼륨 감지**: 임계값(0.02) 이상의 음성만 인식

### Barge-in (끼어들기)
- **TTS 중단 기능**: AI가 응답하는 중에 사용자가 말하면 TTS 자동 중단
- **슬라이딩 윈도우 방식**: 노이즈 필터링을 위한 연속 감지 로직
- **임계값**: 0.025 (민감도 조절 가능)

### 연속 대화 모드
- **자동 녹음 시작**: TTS 완료 후 자동으로 녹음 재개
- **빈 입력 처리**: 연속 2회 빈 입력 시 자동 녹음 일시 중지

### 기타 기능
- AI 응답 및 TTS (Text-to-Speech) 재생
- 실시간 대화 표시
- 상담원 연결 요청

## 기술 스택

- React 19 + TypeScript
- Vite
- Axios
- Web Audio API (AudioContext, ScriptProcessorNode)
- WebSocket (실시간 스트리밍)

## 폴더 구조

```
src/
├── components/
│   ├── VoiceButton.tsx    # 마이크 버튼 컴포넌트
│   ├── VoiceButton.css
│   ├── ChatMessage.tsx    # 메시지 컴포넌트
│   └── ChatMessage.css
├── hooks/
│   ├── useVoiceStream.ts  # 양방향 스트리밍 훅 (VAD, Barge-in, TTS)
│   ├── useRealtimeSTT.ts  # 실시간 STT 훅
│   └── useAudioRecorder.ts # 마이크 녹음 훅
├── services/
│   └── api.ts             # Voice API 연동
├── App.tsx
├── App.css
└── main.tsx
```

## 주요 설정값

| 설정 | 값 | 설명 |
|------|-----|------|
| VAD_SILENCE_THRESHOLD | 0.02 | 음성 감지 볼륨 임계값 |
| VAD_SILENCE_DURATION | 2000ms | 침묵 지속 시간 (자동 전송) |
| BARGE_IN_THRESHOLD | 0.025 | Barge-in 감지 임계값 |
| MIN_VOICE_COUNT | 2 | Barge-in 연속 감지 횟수 |
| MAX_EMPTY_INPUTS | 2 | 연속 빈 입력 허용 횟수 |

## API 연동

### WebSocket
- `ws://localhost:8000/api/v1/voice/streaming/{session_id}` - 양방향 실시간 스트리밍

### REST API
- `POST /api/v1/voice/message` - 음성 메시지 전송 (STT → AI → TTS)
- `POST /api/v1/voice/tts` - TTS 변환
- `POST /api/v1/handover/request` - 상담원 이관 요청
