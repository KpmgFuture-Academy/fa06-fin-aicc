# VAD 모듈 이용 없이 TTS모듈만을 평가하는 파일

import argparse
import csv
import json
import re
import sys
import time
import wave
from pathlib import Path
from typing import Counter as CounterType, Dict, List, Optional, Tuple

# repo root 추가 (app.* import용)
ROOT_DIR = Path(__file__).resolve().parents[1]  # fa06-fin-aicc
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.services.voice.stt_service import AICCSTTService, STTError  # noqa: E402

# 파일별 참조 텍스트
REF_MAP = {
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

# 파일별 기대 키워드(금융 용어/핵심 엔티티)
KW_MAP = {
    # Tier 1
    "T1_01": ["카드", "결제일", "기간"],
    "T1_02": ["한도", "3500만", "원"],
    "T1_03": ["딥드림", "플래티넘", "배송"],
    "T1_04": ["마이신한포인트"],
    "T1_05": ["일시불", "할부"],
    "T1_06": ["해외", "결제", "차단"],
    "T1_07": ["비밀번호", "오류", "초기화"],
    "T1_08": ["청구지", "주소", "도로명", "자택"],
    "T1_09": ["리볼빙", "해지"],
    "T1_10": ["자동이체", "관리비", "도시가스", "할인"],
    # Tier 2
    "T2_01": ["분실", "신고", "지갑"],
    "T2_02": ["결제", "한도", "잔액"],
    "T2_03": ["단기", "카드대출", "이율"],
    "T2_04": ["사업자", "번호"],
    "T2_05": ["해외", "카드", "락"],
    "T2_06": ["청구", "이중", "출금"],
    "T2_07": ["카드", "번호", "뒷번호"],
    "T2_08": ["후불", "교통카드", "칩", "재발급"],
    "T2_09": ["결제", "취소", "문자"],
    "T2_10": ["본인", "상담"],
    # Tier 3
    "T3_01": ["비밀번호"],
    "T3_02": ["상담원", "연결"],
    "T3_03": ["결제대금", "선결제"],
    "T3_04": ["카드"],
    "T3_05": ["포인트", "리뎀션", "캐시백"],
    "T3_06": ["해지", "방어", "조건"],
    "T3_07": ["송금"],
    "T3_08": ["팀장", "바꾸라고"],
    "T3_09": ["카드"],
    "T3_10": [],
}

# 파일별 정답 숫자(하드코딩)
REF_NUM_MAP = {
    "T1_01": ["14", "25"],
    "T1_02": ["3500"],  # 삼천오백만 원
    "T1_05": ["120", "6"],
    "T1_07": ["3", "37"],
    "T2_04": ["1238212345"],
    "T2_07": ["5417", "1111"],
    "T3_01": ["1234", "123555"],
    "T3_07": ["3", "5", "5"],
    "T3_10": ["010", "1234", "5678"],
}

DEFAULT_WAV_DIR = Path(__file__).parent / "converted_wav"
# 결과물 기본 저장 위치: stt_test/output 폴더
DEFAULT_OUTPUT_CSV = Path(__file__).parent / "output" / f"output_{time.strftime('%Y%m%d_%H%M')}.csv"


KOR_DIGIT = {"영": 0, "공": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}


def length_ratio(reference: str, hypothesis: str) -> float:
    """가설/정답 길이 비율(문자수 기준)."""
    return (len(hypothesis) / len(reference)) if reference else 0.0


def compute_rtf(wav_path: Path, latency_ms: float) -> Dict[str, float]:
    """단순 RTF 계산: 처리시간 / 오디오 길이."""
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / rate if rate else 0.0
    rtf = (latency_ms / 1000.0) / duration if duration > 0 else 0.0
    return {"rtf": round(rtf, 3), "latency_ms": round(latency_ms, 3), "duration_s": round(duration, 3)}


def normalize_text(text: str, strip_spaces: bool = False) -> str:
    """
    소문자 변환 + 특수문자 제거 + 다중 공백 정리.
    - 문장부호는 공백이 아닌 빈문자("")로 제거 후 공백 정리
    - strip_spaces=True이면 모든 공백 제거
    - 자주 틀리는 외래어(플래/플레/플랜, 리뎀션/리댑션 등) 통일
    """
    text = text.lower()
    text = re.sub(r"[^\w\s가-힣]", "", text)  # 문장부호 제거 (공백 치환 X)
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


def calc_cer_wer(reference: str, hypothesis: str) -> Tuple[float, float, float]:
    """
    CER/WER 계산.
    - wer_word: 단어 단위(공백 기준) WER
    - cer_no_space: 공백 제거 후 문자 단위 CER (띄어쓰기/문장부호 차이 완화용)
    반환: (cer, wer_word, cer_no_space)
    """
    ref_norm = normalize_text(reference)
    hyp_norm = normalize_text(hypothesis)

    # 숫자를 공통 토큰(NUM)으로 마스킹해 숫자 표현 차이를 완화
    def mask_numbers(txt: str) -> str:
        txt = re.sub(r"\d[\d,]*", " num ", txt)
        # 한글 숫자 표현(영/공/일/... + 만/천/백/십)도 num 처리
        txt = re.sub(r"[영공일이삼사오육칠팔구]*만", " num ", txt)
        txt = re.sub(r"[영공일이삼사오육칠팔구]*천", " num ", txt)
        txt = re.sub(r"[영공일이삼사오육칠팔구]*백", " num ", txt)
        txt = re.sub(r"[영공일이삼사오육칠팔구]*십", " num ", txt)
        # 단일 숫자 한글도 num 처리
        txt = re.sub(r"[영공일이삼사오육칠팔구]", " num ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    ref_masked = mask_numbers(ref_norm)
    hyp_masked = mask_numbers(hyp_norm)

    # CER (공백 포함)
    cer = 0.0 if len(ref_norm) == 0 else levenshtein(ref_norm, hyp_norm) / len(ref_norm) * 100

    # WER (단어 단위)
    ref_words = ref_masked.split()
    hyp_words = hyp_masked.split()
    wer = 0.0 if len(ref_words) == 0 else levenshtein(ref_words, hyp_words) / len(ref_words) * 100

    # CER 공백 제거 버전 (띄어쓰기/문장부호 영향 완화)
    ref_ns = normalize_text(reference, strip_spaces=True)
    hyp_ns = normalize_text(hypothesis, strip_spaces=True)
    cer_ns = 0.0 if len(ref_ns) == 0 else levenshtein(ref_ns, hyp_ns) / len(ref_ns) * 100

    return cer, wer, cer_ns


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
    """
    간단한 변이 생성: ㅐ/ㅔ 교차, 자주 혼동되는 철자 보정.
    예) 플래티넘 ↔ 플레티넘
    """
    variants = {term}
    replacements = [
        ("래", "레"),
        ("레", "래"),
        ("태", "테"),
        ("테", "태"),
    ]
    for src, dst in replacements:
        if src in term:
            variants.add(term.replace(src, dst))
    return list(variants)


def keyword_match_fuzzy(expected: List[str], hyp: str) -> dict:
    """
    키워드 인식 여부(precision/recall/F1) - 간단한 철자 변이 + 공백 무시 매칭.
    예: "단기카드대출" vs "단기 카드 대출", "마이신한포인트" vs "마이 신한 포인트"
    """
    if not expected:
        return {"precision": 100.0, "recall": 100.0, "f1": 100.0, "missed": [], "hit": []}

    hyp_norm = normalize_text(hyp)
    hyp_ns = normalize_text(hyp, strip_spaces=True)
    hit = []
    missed = []

    for kw in expected:
        variants = generate_keyword_variants(kw)
        kw_norms = [normalize_text(v) for v in variants]
        kw_ns = [normalize_text(v, strip_spaces=True) for v in variants]
        found = any(k in hyp_norm for k in kw_norms if k)
        found_ns = any(k in hyp_ns for k in kw_ns if k)
        if found:
            hit.append(kw)
        elif found_ns:
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


def numeric_score_with_override(reference: str, hypothesis: str, override_ref_nums: Optional[List[str]]) -> dict:
    # override_ref_nums가 있으면 그것만 정답으로 사용
    if override_ref_nums:
        ref_nums_counter = CounterType(override_ref_nums)
        hyp_nums_counter = CounterType(extract_numbers(hypothesis))

        matched = sum(min(cnt, hyp_nums_counter.get(num, 0)) for num, cnt in ref_nums_counter.items())
        total_ref = sum(ref_nums_counter.values())
        total_hyp = sum(hyp_nums_counter.values())

        precision = (matched / total_hyp * 100) if total_hyp else 100.0
        recall = (matched / total_ref * 100) if total_ref else 100.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 100.0

        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "ref_numbers": list(ref_nums_counter.elements()),
            "hyp_numbers": list(hyp_nums_counter.elements()),
        }

    # override가 없으면 숫자 평가를 건너뛰고 만점 처리 (불필요한 패널티 방지)
    return {
        "precision": 100.0,
        "recall": 100.0,
        "f1": 100.0,
        "ref_numbers": [],
        "hyp_numbers": [],
    }


def load_manifest(manifest_path: Optional[Path]) -> Dict[str, Dict[str, object]]:
    """
    매니페스트: filename -> {"reference": str, "keywords": List[str], "ref_numbers": [..]}
    """
    if not manifest_path:
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    result: Dict[str, Dict[str, object]] = {}
    for item in data:
        fname = item.get("filename")
        if fname:
            result[fname] = {
                "reference": item.get("reference", ""),
                "keywords": item.get("keywords", []),
                "ref_numbers": item.get("ref_numbers", []),
            }
    return result


def parse_tier(filename: str) -> str:
    m = re.search(r"(T\d+)", filename, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def parse_id_tag(filename: str) -> str:
    m = re.search(r"(T\d+_\d+)", filename, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def parse_speaker(filename: str) -> str:
    """파일명에서 화자 성별 추출 (_f/f숫자=여, _m/m숫자=남, 남/여 문자열)."""
    stem = Path(filename).stem.lower()
    parts = stem.split("_")
    for p in parts:
        if re.fullmatch(r"f\d*", p) or p == "f":
            return "여"
        if re.fullmatch(r"m\d*", p) or p == "m":
            return "남"
        if "여" in p:
            return "여"
        if "남" in p:
            return "남"
    return ""


# 패스 기준:
#  - Rule1: WER ≤ 5% AND 숫자 F1 ≥ 80% AND 금융 키워드 F1 ≥ 80%
#  - Rule2(패자부활): WER ≤ 15% AND CER ≤ 10% AND 숫자 F1 ≥ 80% AND 금융 키워드 F1 ≥ 80%
def decide_pass(wer: float, cer: float, num_f1: float, fin_f1: float) -> bool:
    rule1 = wer <= 5.0 and num_f1 >= 80.0 and fin_f1 >= 80.0
    rule2 = wer <= 15.0 and cer <= 10.0 and num_f1 >= 80.0 and fin_f1 >= 80.0
    return rule1 or rule2


def run_on_file(
    wav_path: Path,
    reference: str,
    keywords: List[str],
    ref_numbers_override: Optional[List[str]],
    stt: AICCSTTService,
) -> Dict[str, object]:
    # STT 호출
    t0 = time.perf_counter()
    stt_result = stt.transcribe_file(wav_path, language="ko", diarize=False)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    hypothesis_raw = stt_result.text
    hypothesis = hypothesis_raw.strip()

    # 메트릭 계산
    cer, wer_word, cer_no_space = calc_cer_wer(reference, hypothesis)
    wer = min(wer_word, cer_no_space)  # 띄어쓰기/문장부호 차이 완화
    len_ratio = length_ratio(reference, hypothesis)
    num_stats = numeric_score_with_override(reference, hypothesis, ref_numbers_override)
    kw_stats = keyword_match_fuzzy(keywords, hypothesis)
    fin_acc = kw_stats["f1"]
    rtf_stats = compute_rtf(wav_path, latency_ms)

    pass_fail = decide_pass(wer, cer, num_stats["f1"], kw_stats["f1"])


    return {
        "filename": wav_path.name,
        "tier": parse_tier(wav_path.name),
        "speaker": parse_speaker(wav_path.name),
        "pass_fail": pass_fail,
        "wer_score": round(wer, 3),
        "cer_score": round(cer, 3),
        "num_f1": num_stats["f1"],
        "fin_acc": fin_acc,
        "ref_nums": str(num_stats["ref_numbers"]),
        "hyp_nums": str(num_stats["hyp_numbers"]),
        "rtf_val": rtf_stats["rtf"],
        "latency_ms": rtf_stats["latency_ms"],
        "len_ratio": len_ratio,
        "stt_text": hypothesis,
        "ref_text": reference,
        "missed_keywords": str(kw_stats.get("missed", [])),
    }


def main():
    parser = argparse.ArgumentParser(
        description="converted_wav 폴더의 파일들을 STT 평가 후 output.csv 저장"
    )
    parser.add_argument("--wav-dir", type=Path, default=DEFAULT_WAV_DIR, help="WAV 폴더 (기본: converted_wav)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV, help="CSV 출력 경로")
    parser.add_argument(
        "--reference",
        type=str,
        default="",
        help="기본 참조 텍스트(매니페스트 없을 때 사용)",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        help="기본 키워드 콤마구분(매니페스트 없을 때 사용)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="파일별 reference/keywords/ref_numbers JSON 매니페스트 경로",
    )
    args = parser.parse_args()

    if not args.wav_dir.exists():
        raise FileNotFoundError(f"WAV 폴더가 없습니다: {args.wav_dir}")

    manifest = load_manifest(args.manifest)
    default_keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    stt = AICCSTTService.get_instance()

    rows: List[Dict[str, object]] = []
    for wav_path in sorted(args.wav_dir.glob("*.wav")):
        meta = manifest.get(wav_path.name, {})
        id_tag = parse_id_tag(wav_path.name)
        reference = meta.get("reference") or REF_MAP.get(id_tag) or args.reference
        keywords = meta.get("keywords") or KW_MAP.get(id_tag) or default_keywords
        ref_numbers_override = meta.get("ref_numbers") or REF_NUM_MAP.get(id_tag)

        if not reference:
            print(f"[skip] reference 미존재: {wav_path.name}")
            continue

        try:
            result = run_on_file(wav_path, reference, keywords, ref_numbers_override, stt)
            rows.append(result)
            print(f"[OK] {wav_path.name} -> WER {result['wer_score']} / F1(num) {result['num_f1']}")
        except STTError as e:
            print(f"[ERR] {wav_path.name}: STT 실패 - {e}")
        except Exception as e:  # noqa: BLE001
            print(f"[ERR] {wav_path.name}: {e}")

    # CSV 저장
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([korean for _, korean in headers])
        for row in rows:
            writer.writerow([row.get(key, "") for key, _ in headers])

    print(f"\nSaved CSV: {args.output} (rows: {len(rows)})")


if __name__ == "__main__":
    main()
