"""
STT 성능(WER/CER) 평가 스크립트.
- 입력 CSV: path,text (음성 파일 경로, 정답 텍스트)
- 엔진: OpenAI Whisper HTTP (필요 시 다른 STT 클라이언트 추가)
"""

import argparse
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from jiwer import wer, cer

# repo 루트 추가 (…/fa06-fin-aicc)
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from app.services.voice1.stt import OpenAIWhisperSTT


def read_manifest(path: Path) -> list[tuple[Path, str]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            audio = Path(row["path"])
            text = row["text"]
            rows.append((audio, text))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="CSV with columns: path,text")
    parser.add_argument("--out", default="stt_eval_results.csv")
    args = parser.parse_args()

    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise SystemExit("OPENAI_API_KEY required")

    stt = OpenAIWhisperSTT(api_key=openai_api_key)
    items = read_manifest(Path(args.manifest))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["engine", "audio_path", "reference", "transcript", "wer", "cer"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for audio_path, ref in items:
            res = stt.transcribe_file(audio_path)
            writer.writerow(
                {
                    "engine": "openai_whisper",
                    "audio_path": str(audio_path),
                    "reference": ref,
                    "transcript": res.text,
                    "wer": wer(ref, res.text),
                    "cer": cer(ref, res.text),
                }
            )
            print(f"[openai_whisper] {audio_path.name} WER={wer(ref, res.text):.3f}")

    print(f"Done. Results -> {args.out}")


if __name__ == "__main__":
    main()
