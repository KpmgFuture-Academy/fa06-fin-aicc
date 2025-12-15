"""원본 학습 데이터 + 증강 데이터 병합 스크립트

원본 42,850개 (38 카테고리) + 증강 데이터 (저성능 카테고리 보강)를 병합합니다.

사용법:
    python scripts/merge_training_data.py
"""

import json
import os
from pathlib import Path
from collections import Counter


# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# 경로 설정
ORIGINAL_TRAINING_DIR = PROJECT_ROOT / "ai_engine" / "ingestion" / "final_hana_card_classifier" / "preprocessed_final" / "Training"
AUGMENTED_DATA_PATH = PROJECT_ROOT / "data" / "augmented_intent_training_data_full.json"
ID2INTENT_PATH = PROJECT_ROOT / "models" / "final_classifier_model" / "model_final" / "id2intent.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "merged_training_data.json"


def load_id2intent():
    """id2intent 매핑 로드"""
    with open(ID2INTENT_PATH, 'r', encoding='utf-8') as f:
        return {int(k): v for k, v in json.load(f).items()}


def load_original_data():
    """원본 학습 데이터 로드"""
    print(f"\n[INFO] 원본 데이터 로드 중: {ORIGINAL_TRAINING_DIR}")

    data = []
    json_files = list(ORIGINAL_TRAINING_DIR.glob("*.json"))

    for i, json_file in enumerate(json_files):
        if i % 5000 == 0:
            print(f"  진행: {i:,}/{len(json_files):,}")

        with open(json_file, 'r', encoding='utf-8') as f:
            file_data = json.load(f)

        for item in file_data:
            # 대화 내용에서 손님 발화만 추출
            text = extract_customer_utterances(item["consulting_content"])
            category = item["consulting_category"]

            if text and category:
                data.append({
                    "text": text,
                    "category": category,
                    "source": "original"
                })

    print(f"[OK] 원본 데이터 로드 완료: {len(data):,}개")
    return data


def extract_customer_utterances(content):
    """대화 내용에서 손님 발화만 추출"""
    lines = content.split('\n')
    customer_texts = []

    for line in lines:
        if line.startswith('손님:'):
            text = line.replace('손님:', '').strip()
            if text and text not in ['네', '네.', '예', '예.', '아', '네네', '응']:
                customer_texts.append(text)

    # 첫 번째 의미있는 발화 사용 (주요 의도가 담긴 부분)
    return ' '.join(customer_texts[:3]) if customer_texts else None


def load_augmented_data():
    """증강 데이터 로드"""
    print(f"\n[INFO] 증강 데이터 로드 중: {AUGMENTED_DATA_PATH}")

    if not AUGMENTED_DATA_PATH.exists():
        print("[WARNING] 증강 데이터 파일이 없습니다")
        return []

    with open(AUGMENTED_DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[OK] 증강 데이터 로드 완료: {len(data):,}개")
    return data


def merge_and_balance(original_data, augmented_data, id2intent):
    """데이터 병합 및 밸런싱"""
    print("\n[INFO] 데이터 병합 중...")

    # intent2id 매핑 생성
    intent2id = {v: k for k, v in id2intent.items()}

    merged = []

    # 원본 데이터 추가
    for item in original_data:
        category = item["category"]
        if category in intent2id:
            merged.append({
                "text": item["text"],
                "intent": category,
                "intent_id": intent2id[category],
                "source": "original"
            })

    # 증강 데이터 추가
    for item in augmented_data:
        intent = item.get("intent", "")
        if intent in intent2id:
            merged.append({
                "text": item["text"],
                "intent": intent,
                "intent_id": intent2id[intent],
                "source": item.get("source", "augmented")
            })

    print(f"[OK] 병합 완료: {len(merged):,}개")

    # 카테고리별 분포 출력
    print("\n[INFO] 카테고리별 분포:")
    category_counts = Counter(item["intent"] for item in merged)

    for intent_id in sorted(id2intent.keys()):
        intent = id2intent[intent_id]
        count = category_counts.get(intent, 0)
        original_count = sum(1 for item in merged if item["intent"] == intent and item["source"] == "original")
        augmented_count = count - original_count
        print(f"  [{intent_id:2d}] {intent:40s}: {count:6,}개 (원본: {original_count:5,}, 증강: {augmented_count:4,})")

    return merged


def save_merged_data(data, output_path):
    """병합 데이터 저장"""
    print(f"\n[INFO] 병합 데이터 저장 중: {output_path}")

    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] 저장 완료: {len(data):,}개 샘플")


def main():
    print("=" * 70)
    print("원본 학습 데이터 + 증강 데이터 병합")
    print("=" * 70)

    # 1. id2intent 로드
    id2intent = load_id2intent()
    print(f"\n[OK] 38개 카테고리 로드 완료")

    # 2. 원본 데이터 로드
    original_data = load_original_data()

    # 3. 증강 데이터 로드
    augmented_data = load_augmented_data()

    # 4. 병합
    merged_data = merge_and_balance(original_data, augmented_data, id2intent)

    # 5. 저장
    save_merged_data(merged_data, OUTPUT_PATH)

    print("\n" + "=" * 70)
    print("[완료] 데이터 병합 완료!")
    print("=" * 70)
    print(f"  원본 데이터: {len(original_data):,}개")
    print(f"  증강 데이터: {len(augmented_data):,}개")
    print(f"  병합 데이터: {len(merged_data):,}개")
    print(f"  저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
