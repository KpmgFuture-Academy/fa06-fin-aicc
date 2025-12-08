# WebSocket Voice Services

HTTP 기반 모듈(`app/services/voice`, `app/services/voice2`)과 별도로, 동일한 퍼블릭 인터페이스를 WebSocket/스트리밍 형태로 제공하는 패키지입니다.

## 구조
- `voice/` : OpenAI Whisper STT WebSocket 버전 (`OpenAIWhisperWebSocketSTT`, `STTWithCustomerEmotionService`, TTS WebSocket 엔진)
- `voice2/` : VITO STT WebSocket 버전 (`ReturnZeroWebSocketSTTEngine`, `VitoSTTWithCustomerEmotionService`)
- `Hume/` : Humelo/Hume TTS HTTP 엔진 (`HumeloTTSHttpEngine`) 및 샘플 스크립트
- `common.py` : WebSocket 공통 유틸(바이너리 프레임 처리, 파싱/스트리밍)

## 의존성
- `websockets` 패키지가 필요합니다(Whisper/VITO WS용). 루트 `requirements.txt`에 포함되어 있으며, 없으면 `pip install websockets`.
- Humelo/Hume TTS는 `HUME_API_KEY`, `HUME_VOICE_ID` 환경변수가 필요합니다. HTTP 엔드포인트는 기본값(`https://prosody-api.humelo.works/api/v1/dive/stream`)을 사용하거나 `HUME_TTS_HTTP_URL`로 오버라이드합니다.

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

## 예시 (Hume/Humelo TTS - HTTP)
```python
import os
from app.services.websocket.Hume.tts3 import HumeloTTSHttpEngine, TextToSpeechService

engine = HumeloTTSHttpEngine(
    api_key=os.environ["HUME_API_KEY"],
    voice_id=os.environ["HUME_VOICE_ID"],
)
tts = TextToSpeechService(engine)
audio = tts.synthesize_to_bytes("안녕하세요. 테스트입니다.")
```
