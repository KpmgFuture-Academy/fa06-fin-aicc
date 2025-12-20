"""
Manual smoke test for Zonos TTS (Korean sample).

Example:
    python zonos_test.py

Requirements:
    - eSpeak NG installed on Windows (phonemizer backend).
    - Environment variables set if installed in a custom path:
        PHONEMIZER_ESPEAK_PATH (e.g., C:\\Program Files\\eSpeak NG\\espeak-ng.exe)
        PHONEMIZER_ESPEAK_LIBRARY (e.g., C:\\Program Files\\eSpeak NG\\libespeak-ng.dll)
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import torch
import torchaudio

from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
from zonos.utils import DEFAULT_DEVICE as device


DEFAULT_TEXT = (
    "테스트 음성입니다. 금융약관 제2조 3항을 참조하면 중도상환 수수료는 3.4%입니다."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a quick Zonos TTS generation.")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Text to synthesize (Korean).")
    parser.add_argument(
        "--speaker-audio",
        default=Path("assets/exampleaudio.mp3"),
        type=Path,
        help="Reference audio to build speaker embedding.",
    )
    parser.add_argument(
        "--model",
        default="Zyphra/Zonos-v0.1-transformer",
        help="Zonos model repo id.",
    )
    parser.add_argument(
        "--language",
        default="ko",
        help="Language code (default: ko).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Where to save the generated wav file.",
    )
    parser.add_argument(
        "--disable-compile",
        action="store_true",
        help="Disable torch.compile during generation (recommended on CPU/Windows).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.speaker_audio.exists():
        raise FileNotFoundError(f"Speaker audio not found: {args.speaker_audio}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.output_dir / f"tts_zonos_{ts}.wav"

    model = Zonos.from_pretrained(args.model, device=device)

    wav, sr = torchaudio.load(args.speaker_audio)
    speaker = model.make_speaker_embedding(wav, sr)

    torch.manual_seed(421)
    cond_dict = make_cond_dict(text=args.text, speaker=speaker, language=args.language)
    conditioning = model.prepare_conditioning(cond_dict)

    codes = model.generate(
        conditioning,
        disable_torch_compile=args.disable_compile,
        progress_bar=False,
    )

    wavs = model.autoencoder.decode(codes).cpu()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(out_path), wavs[0], model.autoencoder.sampling_rate)

    print(f"Saved: {out_path.resolve()}")


if __name__ == "__main__":
    main()
