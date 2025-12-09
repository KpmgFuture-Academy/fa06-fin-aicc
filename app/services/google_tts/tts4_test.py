import os
import sys
import pathlib

# Add project root to sys.path before importing app modules
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

from dotenv import load_dotenv
from app.services.google_tts.tts4 import GoogleTTSEngine, TextToSpeechService

load_dotenv()


def main() -> None:
    api_key = os.getenv("GEM_API_KEY")
    if not api_key:
        raise SystemExit("GEM_API_KEY를 설정하세요")

    engine = GoogleTTSEngine(api_key=api_key)  # ko-KR, ko-KR-Neural2-B 기본
    svc = TextToSpeechService(engine)

    text = "테스트 음성입니다. 금융약관 제2조 3항을 참조하면 중도상환 수수료는 3.4%입니다."
    audio = svc.synthesize_to_bytes(text, format="mp3")
    with open("tts4_test.mp3", "wb") as f:
        f.write(audio)
    print("saved tts4_test.mp3, bytes:", len(audio))


if __name__ == "__main__":
    main()
