import os

from dotenv import load_dotenv
from hume import HumeClient
from hume.tts import FormatMp3, PostedUtterance, PostedUtteranceVoiceWithId

load_dotenv()

api_key = os.getenv("HUME_API_KEY")
if not api_key:
    raise RuntimeError("Set HUME_API_KEY in your environment or .env file")

voice_id = os.getenv("HUME_VOICE_ID")
if not voice_id:
    raise RuntimeError("Set HUME_VOICE_ID (from Voice Library) in your environment or .env file")

text = "고객님의 계좌 잔액은 500만원입니다."

client = HumeClient(api_key=api_key)

utterance = PostedUtterance(
    text=text,
    voice=PostedUtteranceVoiceWithId(id=voice_id, provider="HUME_AI"),
)

audio_stream = client.tts.synthesize_file(
    utterances=[utterance],
    format=FormatMp3(),
)

with open("output.mp3", "wb") as f:
    for chunk in audio_stream:
        f.write(chunk)
