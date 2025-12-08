# WebSocket Voice Services

HTTP 기반 모듈(`app/services/voice`, `app/services/voice2`)과는 별개로, 동일한 퍼블릭 인터페이스를 WebSocket 전송으로 제공하는 복제본입니다. 스트리밍 게이트웨이에 붙일 때 HTTP/WS 인터페이스를 공통으로 유지할 수 있습니다.

## 구조
- `voice/` : OpenAI Whisper STT WebSocket 버전 (`OpenAIWhisperWebSocketSTT`, `STTWithCustomerEmotionService`, TTS WebSocket 엔진)
- `voice2/` : VITO STT WebSocket 버전 (`ReturnZeroWebSocketSTTEngine`, `VitoSTTWithCustomerEmotionService`)
- `Hume/` : Humelo/Hume TTS WebSocket 엔진 (`HumeloTTSWebSocketEngine`) 및 샘플 스크립트
- `common.py` : WebSocket 공통 유틸(프레임 바이너리 처리, 파싱/스트리밍)

## 의존성
- `websockets` 패키지가 필요합니다. 루트 `requirements.txt`에 포함되어 있으며 없으면 `pip install websockets`로 설치합니다.
- Humelo/Hume TTS는 환경변수 `HUME_API_KEY`, `HUME_VOICE_ID`가 필요합니다.

## 예시 (Whisper STT)
```python
import os
from app.services.websocket.voice.stt import OpenAIWhisperWebSocketSTT, SpeechToTextService

engine = OpenAIWhisperWebSocketSTT(
    api_key=os.environ["OPENAI_API_KEY"],
    endpoint="wss://api.openai.com/v1/audio/transcriptions",
)
stt = SpeechToTextService(engine)
result = stt.transcribe_file("sample.wav")
print(result.text)
```

## 예시 (Hume/Humelo TTS)
```python
import os
from app.services.websocket.Hume.tts3 import HumeloTTSWebSocketEngine, TextToSpeechService

engine = HumeloTTSWebSocketEngine(
    api_key=os.environ["HUME_API_KEY"],
    voice_id=os.environ["HUME_VOICE_ID"],
)
tts = TextToSpeechService(engine)
audio = tts.synthesize_to_bytes("안녕하세요, 테스트입니다.")
```
