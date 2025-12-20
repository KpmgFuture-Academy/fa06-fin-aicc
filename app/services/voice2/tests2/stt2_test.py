"""
단순 수동 테스트: VITO STT 서비스 호출 확인.

사용 예:
    python app/services/voice2(VITO)/tests2/stt2_test.py \\
        --api-key <token> \\
        --audio path/to/file.wav
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.voice2 import stt2  # noqa: E402



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", help="VITO API 토큰 (없으면 client-id/secret 필요)")
    parser.add_argument("--client-id", help="VITO Client ID")
    parser.add_argument("--client-secret", help="VITO Client Secret")
    parser.add_argument(
        "--audio",
        type=Path,
        required=True,
        help="전사할 오디오 파일 경로",
    )
    parser.add_argument("--language", default=None, help="선택적 언어 힌트")
    parser.add_argument(
        "--endpoint",
        default="https://openapi.vito.ai/v1/transcribe",
        help="VITO STT 엔드포인트",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.audio.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {args.audio}")

    api_key = args.api_key
    if not api_key:
        if args.client_id and args.client_secret:
            print("API 키가 없어 Client ID/Secret으로 토큰을 발급받습니다...")
            api_key = stt2.authenticate(args.client_id, args.client_secret)
            print(f"토큰 발급 완료: {api_key[:10]}...")
        else:
            raise ValueError("--api-key 또는 (--client-id 와 --client-secret)이 필요합니다.")

    engine = stt2.ReturnZeroSTTEngine(api_key=api_key, endpoint=args.endpoint)
    service = stt2.VitoSpeechToTextService(engine)

    result = service.transcribe_file(args.audio, language=args.language)

    print("=== Raw response ===")
    print(result.raw)
    print("=== Transcription ===")
    print(result.text)
    print(f"Segments: {len(result.segments)}")


if __name__ == "__main__":
    main()
