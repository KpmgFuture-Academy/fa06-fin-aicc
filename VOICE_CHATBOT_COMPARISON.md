# Voice Chatbot vs Voice Chatbot Revision 비교 분석

## 📋 개요

두 폴더는 음성 챗봇의 **서로 다른 버전/구현 방식**을 나타냅니다:
- **`voice-chatbot`**: 기본 버전 (REST API 기반)
- **`frontend_voicebot`**: 개선 버전 (WebSocket 실시간 스트리밍 + Silero VAD)

---

## 🔍 주요 차이점

### 1. **아키텍처 및 통신 방식**

#### `voice-chatbot` (기본 버전)
- **REST API 기반**: `POST /api/v1/voice/message` 엔드포인트 사용
- **배치 처리**: 녹음 완료 후 전체 오디오를 한 번에 전송
- **단방향 통신**: 요청 → 응답 패턴

#### `frontend_voicebot` (개선 버전)
- **WebSocket 기반**: `ws://localhost:8000/api/v1/voice/streaming/{session_id}` 사용
- **실시간 스트리밍**: 오디오를 청크 단위로 실시간 전송
- **양방향 통신**: 오디오 스트리밍 + 실시간 STT 결과 + TTS 스트리밍

---

### 2. **음성 처리 기능**

#### `voice-chatbot`
- ✅ 기본 음성 녹음 및 전송
- ✅ STT (Speech-to-Text)
- ✅ TTS (Text-to-Speech)
- ❌ 실시간 STT 없음
- ❌ VAD (Voice Activity Detection) 없음
- ❌ Barge-in (끼어들기) 없음

#### `frontend_voicebot`
- ✅ **실시간 STT**: VITO API를 통한 실시간 음성 인식
- ✅ **Silero VAD**: 딥러닝 기반 Voice Activity Detection
  - 음성/비음성 자동 구분
  - 2초 침묵 감지 시 자동 전송
  - 노이즈 필터링
- ✅ **Barge-in**: TTS 재생 중 사용자 말하기 감지 및 TTS 중단
- ✅ **연속 대화 모드**: TTS 완료 후 자동 녹음 재개

---

### 3. **프론트엔드 구조**

#### `voice-chatbot`
```
src/
├── hooks/
│   └── useAudioRecorder.ts  # 기본 녹음 훅
├── services/
│   ├── api.ts               # REST API 클라이언트
│   └── websocket.ts         # WebSocket 클라이언트 (사용 안 함)
└── App.tsx                  # 기본 구현
```

#### `frontend_voicebot`
```
src/
├── hooks/
│   ├── useAudioRecorder.ts      # 기본 녹음 훅
│   ├── useRealtimeSTT.ts        # 실시간 STT 훅
│   └── useVoiceStream.ts        # 양방향 스트리밍 훅 (핵심)
├── services/
│   └── api.ts                   # API 클라이언트 (WebSocket 없음)
└── App.tsx                      # 고급 구현
```

---

### 4. **주요 훅 비교**

#### `useAudioRecorder` (공통)
- 두 버전 모두 사용
- 기본 MediaRecorder API 기반 녹음

#### `useVoiceStream` (revision 전용) ⭐
- **실시간 WebSocket 스트리밍**
- **Silero VAD 통합**
- **Barge-in 지원**
- **실시간 STT 결과 표시**
- **TTS 스트리밍 재생**

```typescript
// revision에서 제공하는 기능
const {
  isRecording,
  isConnected,
  isProcessing,
  isPlayingTTS,
  isSpeaking,          // Silero VAD: 말하는 중
  speechProb,          // Silero VAD: 음성 확률 (0.0 ~ 1.0)
  transcript,          // 실시간 STT 텍스트
  finalTranscript,     // 확정된 STT 텍스트
  aiResponse,
  error,
  startRecording,
  stopRecording,
  setOnAutoStop,       // VAD 자동 중지 콜백
  setOnTTSComplete,    // TTS 완료 콜백
  setOnBargeIn,        // Barge-in 콜백
} = useVoiceStream(sessionId);
```

---

### 5. **백엔드 통합**

#### `voice-chatbot`
- REST API 엔드포인트만 사용
- 백엔드 파일 없음

#### `frontend_voicebot`
- WebSocket 스트리밍 엔드포인트 사용
- `backend-files/` 폴더에 백엔드 참조 파일 포함:
  - `app/api/v1/voice_ws.py` - WebSocket 스트리밍 엔드포인트
  - `app/services/voice/stt_service.py` - VITO STT 서비스
  - `app/services/voice/silero_vad_service.py` - Silero VAD 서비스

---

### 6. **사용자 경험 (UX)**

#### `voice-chatbot`
- 녹음 → 중지 → 전송 → 응답 대기 → 재생
- 단계별 처리로 지연 발생 가능
- 실시간 피드백 없음

#### `frontend_voicebot`
- 녹음 시작 → **실시간 STT 텍스트 표시** → 자동 전송 → **TTS 스트리밍 재생**
- 자연스러운 대화 흐름
- **Barge-in**: AI 응답 중에도 끼어들 수 있음
- **연속 대화**: 응답 후 자동으로 다시 녹음 시작

---

### 7. **기술 스택 차이**

#### 공통
- React 19 + TypeScript
- Vite
- Axios
- Web Audio API

#### `frontend_voicebot` 추가
- WebSocket (실시간 통신)
- AudioContext + ScriptProcessorNode (고급 오디오 처리)
- Silero VAD (백엔드 통합)

---

### 8. **설정 및 환경**

#### `voice-chatbot`
- 포트: `3002`
- 스크립트: `npm start` (Vite 설정에 `--port 3002`)

#### `frontend_voicebot`
- 포트: `3010` (README 기준)
- 스크립트: `npm run dev` (기본 포트)
- **VAD 설정**:
  - `VAD_THRESHOLD`: 0.3 (음성 감지 임계값)
  - `SILENCE_DURATION`: 2000ms (침묵 지속 시간)
  - `SAMPLE_RATE`: 16000Hz
  - `MAX_EMPTY_INPUTS`: 2 (연속 빈 입력 허용)

---

## 📊 기능 비교표

| 기능 | voice-chatbot | frontend_voicebot |
|------|---------------|------------------------|
| 음성 녹음 | ✅ | ✅ |
| STT 변환 | ✅ (배치) | ✅ (실시간) |
| TTS 재생 | ✅ (완료 후) | ✅ (스트리밍) |
| WebSocket | ❌ | ✅ |
| 실시간 STT | ❌ | ✅ |
| VAD | ❌ | ✅ (Silero) |
| Barge-in | ❌ | ✅ |
| 연속 대화 | ❌ | ✅ |
| 자동 인사 | ❌ | ✅ |
| 텍스트 채팅 | ❌ | ✅ |

---

## 🎯 언제 어떤 버전을 사용할까?

### `voice-chatbot` 사용 시기
- 간단한 음성 챗봇 프로토타입
- REST API만 지원하는 백엔드
- 실시간 기능이 필요 없는 경우
- 빠른 구현이 필요한 경우

### `frontend_voicebot` 사용 시기
- **프로덕션 수준의 음성 챗봇**
- 자연스러운 대화 경험 필요
- 실시간 피드백 중요
- Barge-in 및 연속 대화 필요
- WebSocket 지원 백엔드

---

## 🔄 마이그레이션 고려사항

`voice-chatbot`에서 `frontend_voicebot`으로 마이그레이션하려면:

1. **백엔드 준비**
   - WebSocket 스트리밍 엔드포인트 구현
   - Silero VAD 서비스 설정
   - VITO STT WebSocket 연동

2. **프론트엔드 변경**
   - `useVoiceStream` 훅으로 전환
   - WebSocket 연결 관리 추가
   - 실시간 STT UI 추가
   - Barge-in 처리 로직 추가

3. **테스트**
   - 실시간 스트리밍 테스트
   - VAD 감지 테스트
   - Barge-in 동작 테스트

---

## 📝 결론

- **`voice-chatbot`**: 기본 구현, REST API 기반, 간단한 사용 사례에 적합
- **`frontend_voicebot`**: 고급 구현, WebSocket 스트리밍 + Silero VAD, 프로덕션 수준의 자연스러운 대화 경험 제공

현재 프로젝트의 메인 백엔드(`app/api/v1/voice_ws.py`)는 `frontend_voicebot`의 요구사항을 지원하는 것으로 보이므로, **revision 버전을 메인으로 사용하는 것이 권장됩니다**.

