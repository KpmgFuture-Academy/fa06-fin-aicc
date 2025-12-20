"""
TTS → STT 역전사 후 WER 측정 스크립트.
- 문장 리스트를 각 TTS 엔진으로 합성 → OpenAI Whisper로 전사 → 원문 대비 WER/CER 계산.
- 결과를 CSV로 저장.
필요 env: OPENAI_API_KEY, (HUME_API_KEY/HUME_VOICE_ID), (GOOGLE_APPLICATION_CREDENTIALS)
"""

import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from jiwer import wer, cer

# repo 루트 추가 (…/fa06-fin-aicc)
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
# Zonos 패키지용 경로 추가
sys.path.insert(0, str(ROOT / "app" / "services" / "Zonos"))

# TTS 엔진들
from app.services.Hume.tts3 import HumeloTTSHttpEngine, TextToSpeechService
from app.services.google_tts.tts4 import GoogleTTSEngine, TextToSpeechService as GoogleTTSService
from app.services.Zonos.zonos import model as zonos_model

# STT(OpenAI Whisper HTTP)
from app.services.voice1.stt import OpenAIWhisperSTT


def read_sentences(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def synthesize(engine_name: str, text: str, out_dir: Path, services: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{engine_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.mp3"
    out_path = out_dir / fname

    if engine_name == "humelo":
        svc: TextToSpeechService = services["humelo"]
        audio = svc.synthesize_to_bytes(text, format="mp3")
        out_path.write_bytes(audio)
    elif engine_name == "google":
        svc: GoogleTTSService = services["google"]
        audio = svc.synthesize_to_bytes(text, voice=None, format="mp3")
        out_path.write_bytes(audio)
    elif engine_name == "zonos":
        # 간단/느리지만 작동하는 sync 경로 (no torch.compile)
        model: zonos_model.Zonos = services["zonos"]["model"]
        speaker = services["zonos"]["speaker"]
        cond_dict = zonos_model.make_cond_dict(text=text, speaker=speaker, language="ko")
        conditioning = model.prepare_conditioning(cond_dict)
        codes = model.generate(conditioning, disable_torch_compile=True, progress_bar=False)
        wavs = model.autoencoder.decode(codes).cpu()
        out_wav = out_path.with_suffix(".wav")
        import torchaudio

        torchaudio.save(str(out_wav), wavs[0], model.autoencoder.sampling_rate)
        return out_wav
    else:
        raise ValueError(f"Unknown engine: {engine_name}")
    return out_path


def transcribe(openai_api_key: str, audio_path: Path) -> str:
    stt = OpenAIWhisperSTT(api_key=openai_api_key)
    res = stt.transcribe_file(audio_path)
    return res.text


def load_zonos(model_id="Zyphra/Zonos-v0.1-transformer", speaker_audio="assets/exampleaudio.mp3"):
    model = zonos_model.Zonos.from_pretrained(model_id, device=zonos_model.DEFAULT_DEVICE)
    import torchaudio

    wav, sr = torchaudio.load(speaker_audio)
    speaker = model.make_speaker_embedding(wav, sr)
    return model, speaker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentences", default="sentences_ko.txt")
    parser.add_argument("--engines", default="humelo,google,zonos")
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--csv", default="tts_eval_results.csv")
    args = parser.parse_args()

    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise SystemExit("OPENAI_API_KEY required for STT back-eval")

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    sentences = read_sentences(Path(args.sentences))
    out_dir = Path(args.out_dir)
    results_csv = Path(args.csv)

    services = {}
    if "humelo" in engines:
        api_key = os.getenv("HUME_API_KEY")
        voice_id = os.getenv("HUME_VOICE_ID")
        if not api_key or not voice_id:
            raise SystemExit("HUME_API_KEY/HUME_VOICE_ID required for humelo engine")
        services["humelo"] = TextToSpeechService(HumeloTTSHttpEngine(api_key=api_key, voice_id=voice_id))
    if "google" in engines:
        services["google"] = GoogleTTSService(GoogleTTSEngine())  # assumes default creds from env
    if "zonos" in engines:
        model, speaker = load_zonos()
        services["zonos"] = {"model": model, "speaker": speaker}

    fieldnames = ["engine", "sentence", "audio_path", "transcript", "wer", "cer", "latency_sec"]
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for text in sentences:
            for engine in engines:
                start = perf_counter()
                audio_path = asyncio.run(synthesize(engine, text, out_dir, services))
                latency = perf_counter() - start
                transcript = transcribe(openai_api_key, audio_path)
                writer.writerow(
                    {
                        "engine": engine,
                        "sentence": text,
                        "audio_path": str(audio_path),
                        "transcript": transcript,
                        "wer": wer(text, transcript),
                        "cer": cer(text, transcript),
                        "latency_sec": round(latency, 3),
                    }
                )
                print(f"[{engine}] saved {audio_path.name}, WER={wer(text, transcript):.3f}")

    print(f"Done. Results -> {results_csv}")


if __name__ == "__main__":
    main()
