# WebSocket Voice Services

HTTP 기반 모듈(`app/services/voice`, `app/services/voice2`)을 그대로 두고, 동일한 퍼블릭 인터페이스를 WebSocket 전송으로 제공하는 복제본이다. 스트리밍 게이트웨이를 붙일 때 이 디렉터리의 모듈을 사용하면 된다.

## 구조
- `voice/` : OpenAI Whisper STT WebSocket 버전 (`OpenAIWhisperWebSocketSTT`, `STTWithCustomerEmotionService`)
- `voice2/` : VITO STT WebSocket 버전 (`ReturnZeroWebSocketSTTEngine`, `VitoSTTWithCustomerEmotionService`)
- `common.py` : WebSocket 공통 유틸(오디오 바이트 정규화, 스트리밍, 타임아웃 처리)

## 의존성
- `websockets` 패키지가 추가로 필요하다. 루트 `requirements.txt`에 포함되어 있지 않으면 `pip install websockets` 후 사용한다.

## 예시 (Whisper)
```python
import os
from app.services.websocket.voice.stt import OpenAIWhisperWebSocketSTT, SpeechToTextService

engine = OpenAIWhisperWebSocketSTT(
    api_key=os.environ["OPENAI_API_KEY"],
    endpoint="wss://api.openai.com/v1/audio/transcriptions",  # 게이트웨이에 맞게 조정
)
stt = SpeechToTextService(engine)
result = stt.transcribe_file("sample.wav")
print(result.text)
```

## 예시 (VITO)
```python
import os
from app.services.websocket.voice2.stt2 import ReturnZeroWebSocketSTTEngine, VitoSpeechToTextService

token = os.environ["VITO_ACCESS_TOKEN"]  # 또는 HTTP auth를 사용해 발급
engine = ReturnZeroWebSocketSTTEngine(api_key=token)
stt = VitoSpeechToTextService(engine)
result = stt.transcribe_file("sample.wav", diarize=True, speaker_count=2)
print(result.text)
```

