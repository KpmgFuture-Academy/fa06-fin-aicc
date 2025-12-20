"""
OpenAI Whisper STT + Content Emotion (CE) 수동 테스트.

예:
  python app/services/voice/tests/stt_w_ce_test.py ^
    --audio path/to/file.wav ^
    --stt-api-key sk-... ^
    --ce-api-key sk-... ^
    --stt-model whisper-1
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.voice1.stt import OpenAIWhisperSTT, SpeechToTextService  # noqa: E402  pylint: disable=wrong-import-position
from app.services.voice1.stt_w_ce import (  # noqa: E402  pylint: disable=wrong-import-position
    OpenAIChatCustomerEmotionClient,
    CustomerEmotionResult,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual test for OpenAI STT + content emotion analysis.")
    parser.add_argument("--audio", type=Path, required=True, help="분석할 오디오 파일 경로")
    parser.add_argument("--language", default=None, help="언어 코드 힌트 (예: ko, en)")
    parser.add_argument("--stt-api-key", help="OpenAI STT API 키 (미지정 시 OPENAI_API_KEY 환경변수)")
    parser.add_argument("--stt-model", default="whisper-1", help="OpenAI STT 모델 (기본 whisper-1)")
    parser.add_argument("--ce-api-key", required=True, help="OpenAI CE(감성 분석) API 키")
    parser.add_argument("--ce-model", default="gpt-4o-mini", help="감성 분석에 사용할 모델")
    parser.add_argument("--ce-endpoint", default="https://api.openai.com/v1/chat/completions", help="OpenAI Chat endpoint")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.audio.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {args.audio}")

    stt_api_key = args.stt_api_key or os.environ.get("OPENAI_API_KEY")
    if not stt_api_key:
        raise SystemExit("ERROR: --stt-api-key 또는 OPENAI_API_KEY 환경변수 중 하나는 필요합니다.")

    stt_engine = OpenAIWhisperSTT(api_key=stt_api_key, model=args.stt_model)
    stt_service = SpeechToTextService(stt_engine)

    ce_client = OpenAIChatCustomerEmotionClient(
        api_key=args.ce_api_key,
        model=args.ce_model,
        endpoint=args.ce_endpoint,
    )

    result = stt_service.transcribe_file(args.audio, language=args.language)
    ce_result: CustomerEmotionResult | None = None
    if result.text:
        ce_result = ce_client.analyze(result.text)

    print("=== Raw STT response ===")
    print(result.raw)
    print("=== Transcription ===")
    print(result.text)
    print(f"Segments: {len(result.segments)}")
    print("=== Segments ===")
    for idx, seg in enumerate(result.segments, 1):
        print(f"[{idx:02d}] text={seg.text} start={seg.start} end={seg.end}")
    print("=== Customer Emotion ===")
    print(ce_result)


if __name__ == "__main__":
    import os

    main()
