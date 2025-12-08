import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("HUME_API_KEY")
if not api_key:
    raise RuntimeError("Set HUME_API_KEY in your environment or .env file")

response = requests.post(
    "https://agitvxptajouhvoatxio.supabase.co/functions/v1/dive-synthesize-v1",
    headers={
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    },
    json={
        "text": "안녕하세요, 시아입니다. 고객님의 계좌 잔액은 500만원입니다.",
        "mode": "preset",
        "voiceName": "시아",
        "emotion": "neutral",
        "lang": "ko",
    },
)

result = response.json()
if result.get("success"):
    print(f"Audio URL: {result['audio_url']}")
else:
    print(f"Error: {result.get('error')}")
