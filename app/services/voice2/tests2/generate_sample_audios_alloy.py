# voice model 변경 : onyx -> alloy
# ce_anger_samples3 폴더에 생성된 음성 저장
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.voice1.tts import OpenAITTSEngine, TextToSpeechService, TTSError


# ----------------------------------------------------------------------
# Anger scale 1~10 샘플 문구 (가이드라인 반영)
# 1~2: 차분/무감정, 불편 없음
# 3~4: 약한 불편/짜증 조짐, 불만 거의 없음
# 5~6: 불만/짜증 표현 시작, 톤이 높아짐, 재촉/압박 시작
# 7~8: 강한 불만·분노, 요구/압박, 공격적 어투 가능
# 9: 매우 격앙, 모욕/폭언 직전 또는 일부 포함, 강한 위협/압박
# 10: 극대노, 노골적 폭언/협박/고함, 대화 단절 직전 수준
# ----------------------------------------------------------------------

ANGER_SAMPLES: list[tuple[int, str]] = [
    (
        1,
        "고객: 안녕하세요. 적금 계좌 잔액이랑 최근 이체 내역만 차분히 확인해 주세요.",
    ),
    (
        2,
        "고객: 수수료가 조금 헷갈리는데, 지금 바로 확인 가능할까요? 급하진 않아요.",
    ),
    (
        3,
        "고객: 어제 출금이 반영이 안 된 것 같은데요. 한 번만 더 확인해 주세요.",
    ),
    (
        4,
        "고객: 문자도 계속 못 받고 있는데, 왜 이렇게 늦나요? 조금 답답하네요.",
    ),
    (
        5,
        "고객: 오늘 안에 처리된다고 하셨잖아요. 지금도 지연이면 문제 있는 거 아닌가요?",
    ),
    (
        6,
        "고객: 몇 번이나 같은 말 반복하는데, 정확히 언제 끝나는지 분명하게 답 주세요.",
    ),
    (
        7,
        "고객: 약속도 어기고, 왜 책임지는 사람이 없습니까? 지금 바로 조치하세요.",
    ),
    (
        8,
        "고객: 계속 이런 식이면 신고하겠습니다. 제 시간 뺏어가면서 처리도 못 하면 어떻게 믿습니까?",
    ),
    (
        9,
        "고객: 지금 장난합니까? 몇 번을 말했는데도 해결 안 하고, 저를 무시하는 건가요?",
    ),
    (
        10,
        "고객: 더는 못 참습니다. 책임자 지금 당장 바꿔요. 계속 이렇게 무시하면 법적 조치하겠습니다.",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate anger-scale TTS samples (1~10).")
    parser.add_argument("--api-key", help="OpenAI TTS API key (미지정 시 OPENAI_API_KEY 환경변수 사용)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "ce_anger_samples3",
        help="생성된 오디오 파일을 저장할 디렉터리",
    )
    parser.add_argument("--voice", default="alloy", help="TTS voice preset (예: alloy)")
    parser.add_argument("--model", default="tts-1", help="OpenAI TTS model (예: tts-1)")
    parser.add_argument(
        "--format",
        default="mp3",
        choices=["mp3", "wav", "ogg"],
        help="출력 오디오 포맷",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: --api-key 또는 OPENAI_API_KEY 환경변수 중 하나는 반드시 필요합니다.")

    engine = OpenAITTSEngine(api_key=api_key, model=args.model)
    service = TextToSpeechService(engine)

    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 출력 디렉터리: {out_dir}")

    for level, text in ANGER_SAMPLES:
        filename = f"ce_anger_level_{level:02d}.{args.format}"
        target_path = out_dir / filename

        print(f"[TTS] level={level:2d} → {target_path.name}")
        try:
            service.synthesize_to_file(
                text=text,
                path=target_path,  # 확장자가 포함되어 있으므로 TTS 서비스가 같은 이름 그대로 저장
                voice=args.voice,
                format=args.format,
            )
        except TTSError as exc:
            raise SystemExit(f"TTS 실패 (level={level}): {exc}") from exc

    print("[DONE] 1~10단계 감정 TTS 샘플 생성 완료!")


if __name__ == "__main__":
    main()
