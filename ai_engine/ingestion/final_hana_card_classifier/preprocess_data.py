"""
데이터 전처리 스크립트
- 원본 데이터(unpacked/)는 수정하지 않음
- 전처리된 데이터를 preprocessed/에 저장
- 텍스트 노이즈 제거 (의미 훼손 없이)
"""
import os
import re
import json
import string
from pathlib import Path
from collections import Counter
from tqdm import tqdm


def clean_text(text):
    """
    안전한 텍스트 전처리 (의미 훼손 없이 노이즈 제거)
    """
    if not text:
        return ""

    # 1. 제어문자 제거 (한글, 영문, 숫자, 기본 특수문자만 유지)
    # printable + 한글(AC00-D7A3) + 한글자모(3130-318F)
    cleaned = []
    for c in text:
        if c in string.printable or '\uAC00' <= c <= '\uD7A3' or '\u3130' <= c <= '\u318F':
            cleaned.append(c)
    text = ''.join(cleaned)

    # 2. 연속 공백 → 단일 공백
    text = re.sub(r"[ \t]+", " ", text)

    # 3. 연속 줄바꿈 → 단일 줄바꿈
    text = re.sub(r"\n+", "\n", text)

    # 4. 연속 특수문자 축약 (예: !!!!! → !, ▲▲▲ → ▲▲▲ 유지)
    # 마스킹 문자(▲)는 제외
    text = re.sub(r"([!?.,;:])\1+", r"\1", text)

    # 5. 앞뒤 공백 제거
    text = text.strip()

    return text


def preprocess_dataset(input_base_dir, output_base_dir):
    """
    전체 데이터셋 전처리
    """
    input_base = Path(input_base_dir)
    output_base = Path(output_base_dir)

    # 통계
    stats = {
        'total_files': 0,
        'processed_files': 0,
        'skipped_files': 0,
        'category_counts': Counter()
    }

    # 모든 JSON 파일 수집 (전체 데이터)
    all_json_files = []
    for root, dirs, files in os.walk(input_base):
        for f in files:
            if f.endswith('.json'):
                all_json_files.append(Path(root) / f)

    print(f"전체 JSON 파일 수: {len(all_json_files)}")
    stats['total_files'] = len(all_json_files)

    # 전처리 진행
    for json_path in tqdm(all_json_files, desc="전처리 중"):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not data or not isinstance(data, list):
                stats['skipped_files'] += 1
                continue

            item = data[0]

            # 필수 필드 확인
            if 'consulting_content' not in item or 'consulting_category' not in item:
                stats['skipped_files'] += 1
                continue

            # 텍스트 전처리
            original_text = item.get('consulting_content', '')
            cleaned_text = clean_text(original_text)

            if not cleaned_text:
                stats['skipped_files'] += 1
                continue

            # 카테고리 정리 (앞뒤 공백 제거)
            category = item.get('consulting_category', '').strip()

            if not category:
                stats['skipped_files'] += 1
                continue

            # 전처리된 데이터 구성
            processed_item = {
                'consulting_content': cleaned_text,
                'consulting_category': category,
                'source': item.get('source', ''),
                'source_id': item.get('source_id', ''),
                'original_length': len(original_text),
                'cleaned_length': len(cleaned_text)
            }

            # 출력 경로 생성 (원본 구조 유지)
            relative_path = json_path.relative_to(input_base)
            output_path = output_base / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump([processed_item], f, ensure_ascii=False, indent=2)

            stats['processed_files'] += 1
            stats['category_counts'][category] += 1

        except Exception as e:
            stats['skipped_files'] += 1
            continue

    return stats


def print_stats(stats):
    """통계 출력"""
    print("\n" + "=" * 60)
    print("전처리 완료 통계")
    print("=" * 60)
    print(f"전체 파일: {stats['total_files']:,}개")
    print(f"처리 완료: {stats['processed_files']:,}개")
    print(f"스킵: {stats['skipped_files']:,}개")
    print(f"\n카테고리 수: {len(stats['category_counts'])}개")

    print("\n" + "=" * 60)
    print("카테고리별 분포 (상위 20개)")
    print("=" * 60)
    for category, count in stats['category_counts'].most_common(20):
        print(f"  {count:>6,}  {category}")

    print("\n" + "=" * 60)
    print("카테고리별 분포 (하위 10개)")
    print("=" * 60)
    for category, count in stats['category_counts'].most_common()[-10:]:
        print(f"  {count:>6,}  {category}")


def main():
    input_dir = Path("./unpacked")
    output_dir = Path("./preprocessed_full")

    print("=" * 60)
    print("데이터 전처리 시작")
    print("=" * 60)
    print(f"입력 경로: {input_dir.absolute()}")
    print(f"출력 경로: {output_dir.absolute()}")
    print("원본 데이터는 수정하지 않습니다.")
    print("=" * 60)

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)

    # 전처리 실행
    stats = preprocess_dataset(input_dir, output_dir)

    # 통계 출력
    print_stats(stats)

    # 통계 파일 저장
    stats_file = output_dir / "preprocessing_stats.txt"
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("전처리 완료 통계\n")
        f.write("=" * 60 + "\n")
        f.write(f"전체 파일: {stats['total_files']:,}개\n")
        f.write(f"처리 완료: {stats['processed_files']:,}개\n")
        f.write(f"스킵: {stats['skipped_files']:,}개\n")
        f.write(f"\n카테고리 수: {len(stats['category_counts'])}개\n\n")
        f.write("카테고리별 분포:\n")
        for category, count in stats['category_counts'].most_common():
            f.write(f"  {count:>6,}  {category}\n")

    print(f"\n통계 파일 저장: {stats_file}")


if __name__ == '__main__':
    main()
