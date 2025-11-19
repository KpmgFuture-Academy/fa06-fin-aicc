import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

import time  # 파일 상단에 추가

@pytest.fixture(scope="module")
def service():
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY가 없어 Whisper 테스트를 건너뜁니다.")
    time.sleep(5)  # 여기서 호출 간격을 확보
    return SpeechToTextService(OpenAIWhisperEngine(api_key=api_key))ㄴ

# 프로젝트 루트(fa06-fin-aicc)를 sys.path에 추가해 모듈 import 문제를 방지한다.
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.voice.stt import (
    DummySTTEngine,
    OpenAIWhisperEngine,
    SpeechToTextService,
)
SAMPLE_AUDIO = Path(__file__).resolve().parent / "fixtures" / "sample.mp3"

@pytest.fixture(scope="module")
def service():
    load_dotenv()  # .env에서 OPENAI_API_KEY 읽기
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY가 없어서 실제 Whisper 테스트를 건너뜁니다.")
    return SpeechToTextService(OpenAIWhisperEngine(api_key=api_key))

def test_dummy_engine_transcription():
    service = SpeechToTextService(DummySTTEngine())
    result = service.transcribe(b"hello world")
    assert result.text
    assert result.language == "ko-KR"

def test_openai_engine_transcription(service):
    # sample.mp3 경로를 프로젝트 기준으로 맞춰주세요.
    result = service.transcribe_file(SAMPLE_AUDIO)
    assert result.text
