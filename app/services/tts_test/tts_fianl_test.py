"""TTS 평가 스크립트 (OpenAI / Google / VibeVoice).
Zonos는 Rust 의존성 문제로 제외.
VibeVoice는 모델/프롬프트가 없으면 자동 스킵합니다.
기존 오디오가 outputs 폴더에 있으면 재사용하여 평가만 수행합니다.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Dict, List

from dotenv import load_dotenv
from jiwer import cer, wer

# repo root 추가
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
# VibeVoice 폴더명은 VibeVoice_main임에 유의
sys.path.insert(0, str(ROOT / "app" / "VibeVoice_main"))

# TTS 엔진들
from app.services.google_tts.tts4 import GoogleTTSEngine, TextToSpeechService as GoogleTTSService
from app.services.voice1.tts import OpenAITTSEngine, TextToSpeechService as OpenAITTSService

# STT(OpenAI Whisper HTTP)
from app.services.voice1.stt import OpenAIWhisperSTT

# 평가 문장 30개
REF_MAP: Dict[str, str] = {
    # Tier 1
    "T1_01": "제 카드 결제일이 14일인데요, 이거 25일로 바꾸면 결제 기간이 언제부터 언제까지인가요?",
    "T1_02": "이번에 결혼 준비 때문에 한도를 좀 크게 올려야 해요. 3500만원까지 가능한가요?",
    "T1_03": "지난주 목요일에 신청한 딥드림 플래티넘 카드, 지금 배송 어디쯤 왔나요?",
    "T1_04": "지금 제가 가지고 있는 마이신한포인트가 총 몇 점인지 확인 좀 해주세요. 소멸 예정인 것도요.",
    "T1_05": "아까 긁은 120만원짜리 결제 건요, 일시불 말고 6개월 할부로 바꿔주실 수 있나요?",
    "T1_06": "제가 당분간 해외 나갈 일이 없어서요, 해외 결제 기능만 일시적으로 차단하고 싶습니다.",
    "T1_07": "비밀번호 3회 오류가 떴다고 해서요. 앞 두 자리는 3, 7인데 초기화해야 하나요?",
    "T1_08": "청구지 주소를 회사에서 자택으로 변경하려고요. 도로명 주소로 불러드리면 되나요?",
    "T1_09": "저 리볼빙 서비스 신청한 적 없는 것 같은데 왜 되어있죠? 이거 당장 해지해 주세요.",
    "T1_10": "아파트 관리비랑 도시가스 요금, 이 카드로 자동이체 신청하면 할인되나요?",
    # Tier 2
    "T2_01": "여보세요? 저 지갑을 잃어버려서요. 분실 신고 좀 하려고 하는데 들리세요?",
    "T2_02": "여기 결제가 자꾸 안 되는데 한도 초과인가요? 잔액은 충분한 것 같은데 확인 좀요.",
    "T2_03": "운전 중이라 길게 통화 못 해요. 단기카드대출 이율만 문자로 좀 찍어주세요.",
    "T2_04": "네, 사업자 번호 불러드릴게요. 1238212345 입니다.",
    "T2_05": "해외여행 중인데 카드가 갑자기 안 긁혀요! 락 걸린 건가요? 급해요 지금.",
    "T2_06": "상담원님, 이번 달 청구 금액에서 이중 출금된 게 있는 것 같아서 전화드렸어요.",
    "T2_07": "잠시만요, 카드 번호가... 5417... 뒷번호는 1111 맞나요?",
    "T2_08": "후불 교통카드 기능이 안 찍혀있어요. 칩이 손상된 건가요? 재발급해야 돼요?",
    "T2_09": "제가 지금 노래방이라 시끄러운데요, 결제 취소 문자 온 게 맞나 해서요.",
    "T2_10": "여보세요? 네, 본인 맞고요. 상담 가능합니다. 말씀하세요.",
    # Tier 3
    "T3_01": "비밀번호가... 1 2 3 4, 아니 아니, 1 2 3 5! 5! 5로 끝나요.",
    "T3_02": "아니 지금 바빠 죽겠는데 상담원 연결이 왜 이렇게 안 돼요? 지금 몇 분째 기다리는 거예요!",
    "T3_03": "그... 뭐냐... 결제대금... 선결제... 하려는데...",
    "T3_04": "카드가 뽀개져가고 다시 만들라 카는데, 우짜면 됩니꺼? 돈 듭니꺼?",
    "T3_05": "이번에 포인트 리뎀션 하려는데 캐시백 율이 어떻게 되나요?",
    "T3_06": "해지 방어 팀 연결해 준다고 하던데... 그게 좀... 조건이...",
    "T3_07": "송금 보낼 건데, 3 보내주세요. 아 5 보낼까? 그냥 5 보내줘요.",
    "T3_08": "당장 팀장 바꾸라고!! 내가 몇 번을 말해야 알아들어!!",
    "T3_09": "제가요 어제 밥을 먹었는데 카드를 냈는데 안 돼서 다른 카드를 냈는데 그건 또 돼서 이게 왜 안 되나 싶어서 전화했거든요?",
    "T3_10": "0 1 0... 1 2 3 4... 5 6 7 8 인데요.",
}


def synthesize_google(svc: GoogleTTSService, text: str, out_path: Path) -> Path:
    audio = svc.synthesize_to_bytes(text, voice=None, format="mp3")
    out_path.write_bytes(audio)
    return out_path


def synthesize_openai(svc: OpenAITTSService, text: str, out_path: Path) -> Path:
    audio = svc.synthesize_to_bytes(text, voice=os.getenv("OPENAI_TTS_VOICE", "alloy"), format="mp3")
    out_path.write_bytes(audio)
    return out_path


def synthesize_vibevoice(vv_obj: dict, text: str, out_path: Path) -> Path:
    import torch
    import torchaudio

    processor = vv_obj["processor"]
    model = vv_obj["model"]
    cached_prompt = vv_obj["prompt"]
    device = vv_obj["device"]

    inputs = processor.process_input_with_cached_prompt(
        text=text,
        cached_prompt=cached_prompt,
        padding=True,
        return_tensors="pt",
        return_attention_mask=True,
    )
    for k, v in inputs.items():
        if torch.is_tensor(v):
            inputs[k] = v.to(device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=None,
        cfg_scale=vv_obj["cfg_scale"],
        tokenizer=processor.tokenizer,
        generation_config={"do_sample": False},
        verbose=False,
        all_prefilled_outputs=cached_prompt,
    )
    speech = outputs.speech_outputs[0].cpu()
    sample_rate = 24000
    torchaudio.save(str(out_path.with_suffix(".wav")), speech, sample_rate)
    return out_path.with_suffix(".wav")


def build_services(args) -> dict:
    services: dict = {}
    # OpenAI
    if "openai" in args.engines:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("OPENAI_API_KEY 필요")
        services["openai"] = OpenAITTSService(
            OpenAITTSEngine(api_key=api_key, model=os.getenv("OPENAI_TTS_MODEL", "tts-1"))
        )
    # Google
    if "google" in args.engines:
        services["google"] = GoogleTTSService(GoogleTTSEngine())
    # VibeVoice (옵션)
    if "vibevoice" in args.engines:
        try:
            vv_root = ROOT / "app" / "VibeVoice_main"
            sys.path.insert(0, str(vv_root))

            from vibevoice.modular.modeling_vibevoice_streaming_inference import (
                VibeVoiceStreamingForConditionalGenerationInference,
            )
            from vibevoice.processor.vibevoice_streaming_processor import VibeVoiceStreamingProcessor
            import torch
            import copy

            # 디바이스/어텐션 설정 (web_tts.py 참고)
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.bfloat16
                attn_impl = "flash_attention_2"
            elif torch.backends.mps.is_available():
                device = "mps"
                dtype = torch.float32
                attn_impl = "sdpa"
            else:
                device = "cpu"
                dtype = torch.float32
                attn_impl = "sdpa"

            model_path = os.getenv("VIBEVOICE_MODEL_PATH", "microsoft/VibeVoice-Realtime-0.5B")
            # 한국어 기본 스피커 우선 (kr-Spk1_man / kr-Spk0_woman 등)
            speaker = os.getenv("VIBEVOICE_SPEAKER", "kr-Spk1_man")

            # 프롬프트 탐색 또는 명시 지정
            voice_prompt = os.getenv("VIBEVOICE_PROMPT_PT")
            if not voice_prompt:
                candidate_dirs = [
                    vv_root / "demo" / "voices" / "streaming_model",
                    Path.home() / "VibeVoice" / "demo" / "voices" / "streaming_model",
                ]
                for d in candidate_dirs:
                    if d.exists():
                        for fname in sorted(d.iterdir()):
                            if fname.suffix == ".pt" and speaker.lower() in fname.stem.lower():
                                voice_prompt = str(fname)
                                break
                    if voice_prompt:
                        break
            if not voice_prompt or not Path(voice_prompt).exists():
                raise RuntimeError(f"VibeVoice prompt (.pt) not found for speaker '{speaker}'")

            processor = VibeVoiceStreamingProcessor.from_pretrained(model_path)
            model = VibeVoiceStreamingForConditionalGenerationInference.from_pretrained(
                model_path,
                torch_dtype=dtype,
                device_map=device if device != "cpu" else None,
                attn_implementation=attn_impl,
            )
            model.to(device)
            prompt = torch.load(voice_prompt, map_location=device, weights_only=False)
            services["vibevoice"] = {
                "processor": processor,
                "model": model,
                "prompt": prompt,
                "device": device,
                "cfg_scale": 1.5,
            }
        except Exception as exc:  # noqa: BLE001
            print(f"[SKIP][vibevoice] init failed: {exc}")
    return services


def transcribe(openai_api_key: str, audio_path: Path) -> str:
    stt = OpenAIWhisperSTT(api_key=openai_api_key)
    res = stt.transcribe_file(audio_path)
    return res.text


async def synthesize(engine: str, text: str, out_dir: Path, services: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{engine}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    out_path = out_dir / fname
    if engine == "openai":
        return synthesize_openai(services["openai"], text, out_path.with_suffix(".mp3"))
    if engine == "google":
        return synthesize_google(services["google"], text, out_path.with_suffix(".mp3"))
    if engine == "vibevoice":
        return synthesize_vibevoice(services["vibevoice"], text, out_path.with_suffix(".wav"))
    raise ValueError(f"Unknown engine: {engine}")


def main():
    parser = argparse.ArgumentParser()
    # 기본: openai, google, vibevoice. 기존 오디오가 있으면 재사용하며 부족분만 합성.
    parser.add_argument("--engines", default="openai,google,vibevoice")
    parser.add_argument("--out-dir", default="app/services/tts_test/outputs")
    parser.add_argument("--csv", default="app/services/tts_test/tts_eval_results.csv")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        default=True,
        help="out-dir에 이미 있는 엔진별 오디오를 재사용해 평가만 수행 (모자라면 합성)",
    )
    args = parser.parse_args()

    load_dotenv()

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    sentences: List[str] = [REF_MAP[k] for k in sorted(REF_MAP.keys())]

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise SystemExit("OPENAI_API_KEY 필요 (STT 역전사용)")

    services = build_services(args)

    out_dir = Path(args.out_dir)
    results_csv = Path(args.csv)
    fieldnames = ["engine", "sentence_id", "sentence", "audio_path", "transcript", "wer", "cer", "latency_sec"]

    def collect_existing(engine: str) -> list[Path]:
        files: list[Path] = []
        for ext in ("mp3", "wav"):
            files.extend(sorted(out_dir.glob(f"{engine}_*.{ext}"), key=lambda p: p.stat().st_mtime))
        return files

    existing_audio: dict[str, list[Path]] = {}
    if args.reuse_existing:
        for eng in engines:
            paths = collect_existing(eng)
            if paths:
                existing_audio[eng] = paths

    with results_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for sid, text in zip(sorted(REF_MAP.keys()), sentences):
            for engine in engines:
                if engine == "vibevoice" and "vibevoice" not in services:
                    print(f"[SKIP][vibevoice][{sid}] service not initialized")
                    continue
                start = perf_counter()
                try:
                    if args.reuse_existing and engine in existing_audio and existing_audio[engine]:
                        audio_path = existing_audio[engine].pop(0)
                        print(f"[REUSE][{engine}][{sid}] {audio_path.name}")
                    else:
                        audio_path = asyncio.run(synthesize(engine, text, out_dir, services))
                except Exception as exc:  # noqa: BLE001
                    print(f"[SKIP][{engine}][{sid}] synth failed: {exc}")
                    continue
                latency = perf_counter() - start
                try:
                    transcript = transcribe(openai_api_key, audio_path)
                except Exception as exc:  # noqa: BLE001
                    print(f"[SKIP][{engine}][{sid}] stt failed: {exc}")
                    continue
                writer.writerow(
                    {
                        "engine": engine,
                        "sentence_id": sid,
                        "sentence": text,
                        "audio_path": str(audio_path),
                        "transcript": transcript,
                        "wer": wer(text, transcript),
                        "cer": cer(text, transcript),
                        "latency_sec": round(latency, 3),
                    }
                )
                print(f"[{engine}][{sid}] saved {audio_path.name}, WER={wer(text, transcript):.3f}")

    print(f"Done. Results -> {results_csv}")


if __name__ == "__main__":
    main()
