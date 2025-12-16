"""
VAD를 적용하여 STT 평가를 수행하는 스크립트.
- 입력: WAV 폴더
- 처리: WebRTC VAD로 음성 구간만 추출 후 STT 호출
- 출력: stt_test/output/output_vad_YYYYMMDD_HHMM.csv
"""

import argparse
import csv
import re
import sys
import time
import wave
from pathlib import Path
from typing import Counter as CounterType, Dict, List, Optional

import numpy as np
from scipy.io import wavfile

# repo root 추가 (app.* import용)
ROOT_DIR = Path(__file__).resolve().parents[1]  # fa06-fin-aicc
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.services.voice.stt_service import AICCSTTService, STTError  # noqa: E402
from app.services.vad.webrtc import WebRTCVADStream  # noqa: E402
from stt_test.final_tts_test import REF_MAP, KW_MAP, REF_NUM_MAP  # noqa: E402

# 기본 경로
DEFAULT_WAV_DIR = Path(__file__).parent / "converted_wav"
DEFAULT_OUTPUT_CSV = Path(__file__).parent / "output" / f"output_vad_{time.strftime('%Y%m%d_%H%M')}.csv"

KOR_DIGIT = {"영": 0, "공": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}


# -------------------------------------------------------------------
# 전처리 / 공통 유틸
# -------------------------------------------------------------------
def normalize_text(text: str, strip_spaces: bool = False) -> str:
    """소문자 변환 + 문장부호 제거(공백 치환 없이) + 다중 공백 정리.
    자주 틀리는 외래어(플래/플레/플랜, 리뎀션/리댑션) 통일."""
    text = text.lower()
    text = re.sub(r"[^\w\s가-힣]", "", text)
    fixes = {
        "플레티넘": "플래티넘",
        "플랜티넘": "플래티넘",
        "리댑션": "리뎀션",
        "리뎀썬": "리뎀션",
    }
    for src, dst in fixes.items():
        text = text.replace(src, dst)
    text = re.sub(r"\s+", " ", text).strip()
    if strip_spaces:
        text = text.replace(" ", "")
    return text


def levenshtein(seq1, seq2) -> int:
    if len(seq1) < len(seq2):
        return levenshtein(seq2, seq1)
    if len(seq2) == 0:
        return len(seq1)
    previous_row = list(range(len(seq2) + 1))
    for i, c1 in enumerate(seq1):
        current_row = [i + 1]
        for j, c2 in enumerate(seq2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def calc_cer_wer(reference: str, hypothesis: str) -> tuple[float, float, float]:
    """CER/WER 계산. (cer, wer_word, cer_no_space)"""
    ref_norm = normalize_text(reference)
    hyp_norm = normalize_text(hypothesis)

    cer = 0.0 if len(ref_norm) == 0 else levenshtein(ref_norm, hyp_norm) / len(ref_norm) * 100

    ref_words = ref_norm.split()
    hyp_words = hyp_norm.split()
    wer = 0.0 if len(ref_words) == 0 else levenshtein(ref_words, hyp_words) / len(ref_words) * 100

    ref_ns = normalize_text(reference, strip_spaces=True)
    hyp_ns = normalize_text(hypothesis, strip_spaces=True)
    cer_ns = 0.0 if len(ref_ns) == 0 else levenshtein(ref_ns, hyp_ns) / len(ref_ns) * 100

    return cer, wer, cer_ns


def length_ratio(reference: str, hypothesis: str) -> float:
    return (len(hypothesis) / len(reference)) if reference else 0.0


def compute_rtf(wav_path: Path, latency_ms: float) -> Dict[str, float]:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / rate if rate else 0.0
    rtf = (latency_ms / 1000.0) / duration if duration > 0 else 0.0
    return {"rtf": round(rtf, 3), "latency_ms": round(latency_ms, 3), "duration_s": round(duration, 3)}


def extract_numbers(text: str) -> List[str]:
    nums: List[str] = []
    for raw in re.findall(r"\d[\d,]*", text):
        nums.append(raw.replace(",", ""))
    for token in re.findall(r"[가-힣]+", text):
        if token.endswith("만") and token[0] in KOR_DIGIT:
            nums.append(str(KOR_DIGIT[token[0]] * 10_000))
        elif token.endswith("천") and token[0] in KOR_DIGIT:
            nums.append(str(KOR_DIGIT[token[0]] * 1_000))
        elif token.endswith("백") and token[0] in KOR_DIGIT:
            nums.append(str(KOR_DIGIT[token[0]] * 100))
        elif token.endswith("십") and token[0] in KOR_DIGIT:
            nums.append(str(KOR_DIGIT[token[0]] * 10))
        elif token in KOR_DIGIT:
            nums.append(str(KOR_DIGIT[token]))
    return nums


def generate_keyword_variants(term: str) -> List[str]:
    variants = {term}
    replacements = [("래", "레"), ("레", "래"), ("태", "테"), ("테", "태")]
    for src, dst in replacements:
        if src in term:
            variants.add(term.replace(src, dst))
    return list(variants)


def keyword_match_fuzzy(expected: List[str], hyp: str) -> dict:
    if not expected:
        return {"precision": 100.0, "recall": 100.0, "f1": 100.0, "missed": [], "hit": []}

    hyp_norm = normalize_text(hyp)
    hyp_ns = normalize_text(hyp, strip_spaces=True)
    hit, missed = [], []

    for kw in expected:
        variants = generate_keyword_variants(kw)
        kw_norms = [normalize_text(v) for v in variants]
        kw_ns = [normalize_text(v, strip_spaces=True) for v in variants]
        found = any(k in hyp_norm for k in kw_norms if k) or any(k in hyp_ns for k in kw_ns if k)
        if found:
            hit.append(kw)
        else:
            missed.append(kw)

    precision = (len(hit) / len(expected) * 100) if expected else 0.0
    recall = (len(hit) / len(expected) * 100) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "missed": missed,
        "hit": hit,
    }


def numeric_match_score(hyp: str, ref_numbers: List[str]) -> dict:
    if not ref_numbers:
        return {"precision": 100.0, "recall": 100.0, "f1": 100.0, "ref_numbers": [], "hyp_numbers": []}

    ref_counter = CounterType(ref_numbers)
    hyp_counter = CounterType(extract_numbers(hyp))

    matched = sum(min(cnt, hyp_counter.get(num, 0)) for num, cnt in ref_counter.items())
    total_ref = sum(ref_counter.values())
    total_hyp = sum(hyp_counter.values())

    precision = (matched / total_hyp * 100) if total_hyp else 100.0
    recall = (matched / total_ref * 100) if total_ref else 100.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 100.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "ref_numbers": list(ref_counter.elements()),
        "hyp_numbers": list(hyp_counter.elements()),
    }


# -------------------------------------------------------------------
# VAD 적용
# -------------------------------------------------------------------
def apply_vad(input_path: Path) -> Path:
    """WebRTC VAD로 음성 구간만 추출한 임시 WAV를 반환."""
    sample_rate, data = wavfile.read(input_path)
    if len(data.shape) > 1:
        data = data[:, 0]  # 모노 변환
    if sample_rate != 16000:
        raise ValueError("VAD 입력 WAV는 16kHz여야 합니다.")

    frame_ms = 30
    frame_len = int(sample_rate * frame_ms / 1000)
    vad = WebRTCVADStream(sample_rate=sample_rate, frame_ms=frame_ms)

    speech_segments = []
    for i in range(0, len(data), frame_len):
        chunk = data[i : i + frame_len].tobytes()
        for fr in vad.feed(chunk):
            if fr.is_speech:
                start = int(fr.start_ms * sample_rate / 1000)
                end = int(fr.end_ms * sample_rate / 1000)
                speech_segments.append(data[start:end])

    if speech_segments:
        out_data = np.concatenate(speech_segments)
    else:
        out_data = np.array([], dtype=data.dtype)

    out_path = input_path.parent / "temp_vad_output.wav"
    wavfile.write(out_path, sample_rate, out_data)
    return out_path


# -------------------------------------------------------------------
# 평가
# -------------------------------------------------------------------
def decide_pass(wer: float, cer: float, num_f1: float, fin_f1: float) -> bool:
    rule1 = wer <= 5.0 and num_f1 >= 80.0 and fin_f1 >= 80.0
    rule2 = wer <= 15.0 and cer <= 10.0 and num_f1 >= 80.0 and fin_f1 >= 80.0
    return rule1 or rule2


def run_on_file(wav_path: Path, use_vad: bool, stt: AICCSTTService) -> Dict[str, object]:
    # 참조 메타 - 파일명에서 T1_01 같은 ID 추출
    id_tag = re.search(r"(T\d+_\d+)", wav_path.name, re.IGNORECASE)
    id_tag = id_tag.group(1).upper() if id_tag else ""
    reference = REF_MAP.get(id_tag, "")
    keywords = KW_MAP.get(id_tag, [])
    ref_numbers = REF_NUM_MAP.get(id_tag, [])

    if not reference:
        raise ValueError(f"reference 없음: {wav_path.name}")

    target_path = apply_vad(wav_path) if use_vad else wav_path

    # STT 호출
    t0 = time.perf_counter()
    stt_result = stt.transcribe_file(target_path, language="ko", diarize=False)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    hypothesis = stt_result.text.strip()

    # 메트릭
    cer, wer_word, cer_ns = calc_cer_wer(reference, hypothesis)
    wer = min(wer_word, cer_ns)
    len_r = length_ratio(reference, hypothesis)
    num_stats = numeric_match_score(hypothesis, ref_numbers)
    kw_stats = keyword_match_fuzzy(keywords, hypothesis)
    rtf_stats = compute_rtf(target_path, latency_ms)

    pass_fail = decide_pass(wer, cer, num_stats["f1"], kw_stats["f1"])

    filename_col = wav_path.name
    if use_vad:
        stem, suf = Path(wav_path.name).stem, Path(wav_path.name).suffix
        filename_col = f"{stem}_with_vad{suf}"

    return {
        "filename": filename_col,
        "tier": id_tag.split("_")[0] if "_" in id_tag else "",
        "speaker": "",  # 필요 시 parse_speaker 로 확장
        "pass_fail": pass_fail,
        "wer_score": round(wer, 3),
        "cer_score": round(cer, 3),
        "num_f1": num_stats["f1"],
        "fin_acc": kw_stats["f1"],
        "ref_nums": str(num_stats["ref_numbers"]),
        "hyp_nums": str(num_stats["hyp_numbers"]),
        "rtf_val": rtf_stats["rtf"],
        "latency_ms": rtf_stats["latency_ms"],
        "len_ratio": len_r,
        "missed_keywords": str(kw_stats.get("missed", [])),
        "stt_text": hypothesis,
        "ref_text": reference,
    }


def main():
    parser = argparse.ArgumentParser(description="VAD 적용 STT 평가")
    parser.add_argument("--wav-dir", type=Path, default=DEFAULT_WAV_DIR, help="WAV 폴더")
    parser.add_argument("--use-vad", action="store_true", help="VAD 적용 여부")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV, help="CSV 출력 경로")
    args = parser.parse_args()

    if not args.wav_dir.exists():
        raise FileNotFoundError(f"WAV 폴더가 없습니다: {args.wav_dir}")

    stt = AICCSTTService.get_instance()
    rows: List[Dict[str, object]] = []

    for wav_path in sorted(args.wav_dir.glob("*.wav")):
        try:
            rows.append(run_on_file(wav_path, args.use_vad, stt))
            print(f"[OK] {wav_path.name}")
        except Exception as e:  # noqa: BLE001
            print(f"[ERR] {wav_path.name}: {e}")

    # CSV 저장
    args.output.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        ("filename", "파일명"),
        ("tier", "테스트 단계"),
        ("speaker", "화자"),
        ("pass_fail", "최종 결과"),
        ("wer_score", "WER (단어오류)"),
        ("cer_score", "CER (문자오류)"),
        ("num_f1", "숫자 정확도(F1)"),
        ("fin_acc", "금융용어 정확도"),
        ("ref_nums", "정답 숫자"),
        ("hyp_nums", "인식 숫자"),
        ("rtf_val", "응답 속도(RTF)"),
        ("latency_ms", "지연 시간(ms)"),
        ("len_ratio", "길이 비율"),
        ("stt_text", "STT 인식 텍스트"),
        ("ref_text", "참조 텍스트"),
        ("missed_keywords", "미인식 키워드"),
    ]
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([k for _, k in headers])
        for row in rows:
            writer.writerow([row.get(key, "") for key, _ in headers])

    print(f"\nSaved CSV: {args.output} (rows: {len(rows)})")


if __name__ == "__main__":
    main()

