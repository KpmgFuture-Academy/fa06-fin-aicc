import sys
import pathlib
import os
import asyncio

from dotenv import load_dotenv

from app.services.websocket.Hume.tts3 import HumeloTTSHttpEngine, TextToSpeechService

# 프로젝트 루트를 PYTHONPATH에 추가 (스크립트 단독 실행 시 필요)
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

load_dotenv()


async def main() -> None:
    api_key = os.getenv("HUME_API_KEY")
    voice_id = os.getenv("HUME_VOICE_ID")
    if not api_key or not voice_id:
        raise SystemExit("Set HUME_API_KEY and HUME_VOICE_ID first")

    engine = HumeloTTSHttpEngine(
        api_key=api_key,
        voice_id=voice_id,
        # endpoint 기본값: https://prosody-api.humelo.works/api/v1/dive/stream
        # 필요 시 HUME_TTS_HTTP_URL 환경변수로 오버라이드
    )
    svc = TextToSpeechService(engine)

    text = "안녕하세요. 테스트 음성입니다. 금융약관 제 2조 3항을 참고하시면 중도상환 수수료는 3.2%입니다."
    audio_bytes = await svc.synthesize_to_bytes_async(text, voice=voice_id, format="mp3")
    with open("tts3_test.mp3", "wb") as f:
        f.write(audio_bytes)
    print("done:", len(audio_bytes), "bytes")


if __name__ == "__main__":
    asyncio.run(main())
