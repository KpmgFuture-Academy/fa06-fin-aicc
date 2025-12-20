"""
VITO STT + CE(Content Emotion) 수동 테스트 스크립트.

예:
  python app/services/voice2/tests2/stt2_w_ce_test.py ^
    --audio path/to/file.wav ^
    --client-id <vito_id> --client-secret <vito_secret> ^
    --openai-api-key sk-... ^
    --customer-speaker 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.voice2 import stt2_w_ce as stt2  # noqa: E402  pylint: disable=wrong-import-position


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", help="VITO API 키 (또는 client-id/secret 필요)")
    parser.add_argument("--client-id", help="VITO Client ID")
    parser.add_argument("--client-secret", help="VITO Client Secret")
    parser.add_argument("--openai-api-key", required=True, help="OpenAI API 키 (감성 분석용)")
    parser.add_argument("--ce-model", default="gpt-4o-mini", help="감성 분석에 사용할 모델")
    parser.add_argument("--ce-endpoint", default="https://api.openai.com/v1/chat/completions", help="OpenAI Chat endpoint")
    parser.add_argument("--audio", type=Path, required=True, help="분석할 오디오 파일 경로")
    parser.add_argument("--language", default=None, help="언어 코드 힌트")
    parser.add_argument("--speaker-count", type=int, default=None, help="화자 수 힌트 (diarization 사용 시)")
    parser.add_argument("--customer-speaker", default="1", help="고객 화자 ID (기본 '1')")
    parser.add_argument("--no-diarize", action="store_true", help="화자 분리 사용 안 함")
    parser.add_argument("--endpoint", default="https://openapi.vito.ai/v1/transcribe", help="VITO STT 엔드포인트")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.audio.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {args.audio}")

    api_key = args.api_key
    if not api_key:
        if args.client_id and args.client_secret:
            print("API 키가 없어 Client ID/Secret으로 토큰을 요청합니다...")
            api_key = stt2.authenticate(args.client_id, args.client_secret)
            print(f"토큰 요청 완료: {api_key[:10]}...")
        else:
            raise ValueError("--api-key 또는 (--client-id 와 --client-secret)이 필요합니다.")

    engine = stt2.ReturnZeroSTTEngine(api_key=api_key, endpoint=args.endpoint)
    emotion_client = stt2.OpenAIChatCustomerEmotionClient(
        api_key=args.openai_api_key,
        model=args.ce_model,
        endpoint=args.ce_endpoint,
    )
    service = stt2.VitoSTTWithCustomerEmotionService(
        engine,
        emotion_client,
        customer_speaker=args.customer_speaker,
    )

    result = service.transcribe_and_analyze(
        args.audio,
        language=args.language,
        diarize=not args.no_diarize,  # 기본 True, --no-diarize 주면 False
        speaker_count=args.speaker_count,
        customer_speaker=args.customer_speaker,
    )

    print("=== Raw STT response ===")
    print(result.transcription.raw)
    print("=== Transcription ===")
    print(result.transcription.text)
    print(f"Segments: {len(result.transcription.segments)}")
    print("=== Segments (with speaker) ===")
    for idx, seg in enumerate(result.transcription.segments, 1):
        speaker = seg.speaker or "?"
        print(f"[{idx:02d}] speaker={speaker} text={seg.text}")
    print("=== Customer Emotion ===")
    print(result.emotion)


if __name__ == "__main__":
    main()
