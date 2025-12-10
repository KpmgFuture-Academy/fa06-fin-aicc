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
npm run dev
```
[http://localhost:3010](http://localhost:3010)에서 확인할 수 있습니다.

### 3. 백엔드 서버
백엔드 서버가 `http://localhost:8000`에서 실행 중이어야 합니다.

## 주요 기능

### 실시간 음성 스트리밍
- **양방향 WebSocket 스트리밍**: STT + AI 응답 + TTS를 단일 연결로 처리
- **실시간 STT**: VITO API를 통한 실시간 음성 인식

### VAD (Voice Activity Detection) - Silero VAD
- **딥러닝 기반 VAD**: Silero VAD 모델을 사용한 정확한 음성/비음성 구분
- **2초 침묵 감지**: 사용자가 말을 멈추면 자동으로 전송
- **노이즈 필터링**: 키보드 소리, 배경 소음 등 비음성 자동 필터링
- **실시간 음성 확률**: 0.0 ~ 1.0 범위의 음성 확률 반환

### Barge-in (끼어들기)
- **TTS 중단 기능**: AI가 응답하는 중에 사용자가 말하면 TTS 자동 중단
- **Silero VAD 기반**: 딥러닝 모델로 정확한 Barge-in 감지
- **오디오 캡처 유지**: TTS 재생 중에도 VAD 감지 계속 활성화

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
voice-chatbot-revision/
├── src/
│   ├── components/
│   │   ├── VoiceButton.tsx    # 마이크 버튼 컴포넌트
│   │   ├── VoiceButton.css
│   │   ├── ChatMessage.tsx    # 메시지 컴포넌트
│   │   └── ChatMessage.css
│   ├── hooks/
│   │   ├── useVoiceStream.ts  # 양방향 스트리밍 훅 (Silero VAD, Barge-in, TTS)
│   │   ├── useRealtimeSTT.ts  # 실시간 STT 훅
│   │   └── useAudioRecorder.ts # 마이크 녹음 훅
│   ├── services/
│   │   └── api.ts             # Voice API 연동
│   ├── App.tsx
│   ├── App.css
│   └── main.tsx
└── backend-files/             # 백엔드 참조 파일 (복사본)
    └── app/
        ├── main.py
        ├── api/v1/
        │   └── voice_ws.py        # WebSocket 스트리밍 엔드포인트
        └── services/voice/
            ├── __init__.py
            ├── stt_service.py     # VITO STT 서비스
            └── silero_vad_service.py  # Silero VAD 서비스
```

## 주요 설정값

| 설정 | 값 | 설명 |
|------|-----|------|
| VAD_THRESHOLD | 0.3 | Silero VAD 음성 감지 임계값 (0.0 ~ 1.0) |
| SILENCE_DURATION | 2000ms | 침묵 지속 시간 (자동 전송) |
| SAMPLE_RATE | 16000Hz | 오디오 샘플레이트 |
| MAX_EMPTY_INPUTS | 2 | 연속 빈 입력 허용 횟수 |

## API 연동

### WebSocket
- `ws://localhost:8000/api/v1/voice/streaming/{session_id}` - 양방향 실시간 스트리밍

### REST API
- `POST /api/v1/voice/message` - 음성 메시지 전송 (STT → AI → TTS)
- `POST /api/v1/voice/tts` - TTS 변환
- `POST /api/v1/handover/request` - 상담원 이관 요청
