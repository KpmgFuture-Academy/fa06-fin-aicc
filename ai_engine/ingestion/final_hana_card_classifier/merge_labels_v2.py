"""
추가 레이블 병합 스크립트 (v2)
- 오류 분석 결과 기반 추가 병합
- F1=0 카테고리 해결
"""
import os
import json
import shutil
from pathlib import Path
from collections import Counter

# 추가 병합 규칙 (오류 분석 기반)
MERGE_RULES_V2 = {
    # F1=0 카테고리 병합
    "서비스 이용방법 안내": "이용방법 안내",
    "안심클릭/▲▲페이/기타페이 안내": "이용방법 안내",

    # 소수 클래스 + 의미 유사 병합
    "소득공제 확인서/종합소득세 안내": "증명서/확인서 발급",
    "명세서 재발송": "증명서/확인서 발급",
}


def merge_labels(input_dir: Path, output_dir: Path):
    """레이블 병합 실행"""

    # 출력 디렉토리 생성
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # 통계
    total_files = 0
    merged_count = Counter()
    category_count = Counter()

    # 모든 파일 처리
    for split in ['Training', 'Validation']:
        input_split = input_dir / split
        output_split = output_dir / split

        if not input_split.exists():
            continue

        output_split.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(input_split):
            for filename in files:
                if not filename.endswith('.json'):
                    continue

                filepath = Path(root) / filename

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    original_category = data[0].get('consulting_category', '').strip()

                    # 병합 규칙 적용
                    if original_category in MERGE_RULES_V2:
                        new_category = MERGE_RULES_V2[original_category]
                        data[0]['consulting_category'] = new_category
                        merged_count[f"{original_category} → {new_category}"] += 1
                    else:
                        new_category = original_category

                    # 카테고리별 카운트
                    category_count[new_category] += 1

                    # 저장
                    output_path = output_split / filename
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    total_files += 1

                except Exception as e:
                    print(f"오류: {filepath} - {e}")
                    continue

    return total_files, merged_count, category_count


def main():
    input_dir = Path('./preprocessed_augmented')
    output_dir = Path('./preprocessed_final')

    print("=" * 60)
    print("추가 레이블 병합 (v2)")
    print("=" * 60)
    print("\n병합 규칙:")
    for src, dst in MERGE_RULES_V2.items():
        print(f"  {src} → {dst}")

    print(f"\n입력: {input_dir}")
    print(f"출력: {output_dir}")

    # 병합 실행
    total_files, merged_count, category_count = merge_labels(input_dir, output_dir)

    # 카테고리 파일 생성
    categories = sorted(category_count.keys())
    with open(output_dir / 'categories.txt', 'w', encoding='utf-8') as f:
        for cat in categories:
            f.write(f"{cat}\n")

    # 통계 출력 및 저장
    print(f"\n{'=' * 60}")
    print("병합 완료 통계")
    print(f"{'=' * 60}")
    print(f"전체 파일: {total_files:,}개")
    print(f"카테고리 수: {len(categories)}개")

    print(f"\n병합 적용 내역:")
    for merge_info, count in sorted(merged_count.items(), key=lambda x: -x[1]):
        print(f"  {count:>6}개  {merge_info}")

    print(f"\n최종 카테고리 분포:")
    for cat, count in sorted(category_count.items(), key=lambda x: -x[1]):
        print(f"  {count:>6}  {cat}")

    # 통계 파일 저장
    with open(output_dir / 'merge_stats_v2.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("추가 레이블 병합 (v2) 통계\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"전체 파일: {total_files:,}개\n")
        f.write(f"카테고리 수: {len(categories)}개\n\n")

        f.write("병합 규칙:\n")
        for src, dst in MERGE_RULES_V2.items():
            f.write(f"  {src} → {dst}\n")

        f.write(f"\n병합 적용 내역:\n")
        for merge_info, count in sorted(merged_count.items(), key=lambda x: -x[1]):
            f.write(f"  {count:>6}개  {merge_info}\n")

        f.write(f"\n최종 카테고리 분포:\n")
        for cat, count in sorted(category_count.items(), key=lambda x: -x[1]):
            f.write(f"  {count:>6}  {cat}\n")

    print(f"\n통계 저장: {output_dir / 'merge_stats_v2.txt'}")
    print(f"카테고리 파일: {output_dir / 'categories.txt'}")


if __name__ == '__main__':
    main()
