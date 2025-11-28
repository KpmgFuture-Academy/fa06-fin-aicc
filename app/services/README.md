# Services Overview

음성 관련 세 가지 서비스를 한눈에 설명합니다. 먼저 프로젝트의 기본 의존성 설치를 완료하세요(`pip install -r requirements.txt` 또는 프로젝트 표준 절차).

## voice — OpenAI Whisper STT + OpenAI TTS
- 주요 파일: `stt.py`, `stt_w_ce.py`(confidence/segment 확장), `tts.py`, `tts_onyx.py`
- 필요 환경 변수: `OPENAI_API_KEY`
- STT 예시:
  ```python
  import os
  from app.services.voice.stt import OpenAIWhisperSTT, SpeechToTextService

  stt = SpeechToTextService(OpenAIWhisperSTT(api_key=os.environ["OPENAI_API_KEY"]))
  result = stt.transcribe_file("sample.wav")
  print(result.text)
  ```
- TTS 예시:
  ```python
  import os
  from app.services.voice.tts import OpenAITTSEngine

  engine = OpenAITTSEngine(api_key=os.environ["OPENAI_API_KEY"])
  audio = engine.synthesize("안녕하세요", voice="alloy", format="mp3").audio
  with open("out.mp3", "wb") as f:
      f.write(audio)
  ```
- 테스트: `pytest app/services/voice/tests`

## voice2 — VITO STT (diarization 지원)
- 주요 파일: `stt2.py`(VITO STT), `stt2_w_ce.py`(메타 포함 확장)
- 필요 환경 변수: `VITO_CLIENT_ID`, `VITO_CLIENT_SECRET`
- 예시:
  ```python
  import os
  from app.services.voice2.stt2 import authenticate, VitoSTTService, VitoSTTEngine

  token = authenticate(os.environ["VITO_CLIENT_ID"], os.environ["VITO_CLIENT_SECRET"])
  engine = VitoSTTEngine(token)
  stt = VitoSTTService(engine)
  result = stt.transcribe_file("sample.wav", diarization=True)
  print(result.text)
  ```
- 테스트: `pytest app/services/voice2/tests2`

## Zonos — Voice conversion demo
- 세부 문서는 `app/services/Zonos/README.md` 참고
- 주요 파일: `gradio_interface.py`, `docker-compose.yml`, `Dockerfile`, `pyproject.toml`
- 로컬 실행 예시:
  ```bash
  cd app/services/Zonos
  python -m venv .venv && .venv\Scripts\activate
  pip install -e .
  python gradio_interface.py
  ```
- Docker 실행 예시:
  ```bash
  cd app/services/Zonos
  docker-compose up --build
  ```
- 샘플 오디오: `sample.wav`, `sadness_audio.wav`, `zonos_test_audio.wav`
