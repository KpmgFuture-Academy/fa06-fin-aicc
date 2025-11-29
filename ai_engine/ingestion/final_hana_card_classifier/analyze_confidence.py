"""
Confidence 분포 분석 스크립트
- 검증 데이터에서 모델 예측의 confidence 분포 확인
- A/B/C 패턴 임계값 설정 기준 제공
"""
import os
import json
import torch
import numpy as np
from pathlib import Path
from transformers import ElectraTokenizer, ElectraForSequenceClassification
from peft import PeftModel
from tqdm import tqdm

def load_model(model_dir: str, category_file: str):
    """LoRA 모델 로드"""
    with open(category_file, 'r', encoding='utf-8') as f:
        categories = [line.strip() for line in f if line.strip()]

    tokenizer = ElectraTokenizer.from_pretrained("beomi/KcELECTRA-base-v2022")

    base_model = ElectraForSequenceClassification.from_pretrained(
        "beomi/KcELECTRA-base-v2022",
        num_labels=len(categories)
    )

    lora_path = os.path.join(model_dir, 'lora_adapter')
    model = PeftModel.from_pretrained(base_model, lora_path)
    model = model.merge_and_unload()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    model.eval()

    return model, tokenizer, categories, device

def load_validation_data(val_dir: str):
    """검증 데이터 로드"""
    samples = []
    for root, dirs, files in os.walk(val_dir):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            filepath = Path(root) / filename
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                text = data[0].get('consulting_content', '')
                category = data[0].get('consulting_category', '')
                if text and category:
                    samples.append({'text': text, 'label': category})
            except:
                continue
    return samples

def analyze_confidence(
    model_dir: str = './model_final',
    val_dir: str = './preprocessed_final/Validation',
    category_file: str = './preprocessed_final/categories.txt'
):
    """Confidence 분포 분석"""

    print("모델 로드 중...")
    model, tokenizer, categories, device = load_model(model_dir, category_file)
    cat_to_idx = {cat: idx for idx, cat in enumerate(categories)}

    print("검증 데이터 로드 중...")
    samples = load_validation_data(val_dir)
    print(f"검증 샘플 수: {len(samples)}")

    # Confidence 수집
    confidences = []
    correct_confidences = []
    wrong_confidences = []

    print("\n예측 수행 중...")
    for sample in tqdm(samples):
        text = sample['text']
        true_label = sample['label']

        # 토크나이즈
        inputs = tokenizer(
            text,
            max_length=256,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        ).to(device)

        # 예측
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            confidence, pred_idx = torch.max(probs, dim=-1)
            confidence = confidence.item()
            pred_idx = pred_idx.item()

        pred_label = categories[pred_idx]
        is_correct = (pred_label == true_label)

        confidences.append(confidence)
        if is_correct:
            correct_confidences.append(confidence)
        else:
            wrong_confidences.append(confidence)

    # 분석
    confidences = np.array(confidences)
    correct_confidences = np.array(correct_confidences)
    wrong_confidences = np.array(wrong_confidences)

    print("\n" + "=" * 60)
    print("Confidence 분포 분석")
    print("=" * 60)

    # 전체 통계
    print(f"\n전체 샘플: {len(confidences)}")
    print(f"  Mean: {np.mean(confidences):.4f}")
    print(f"  Std:  {np.std(confidences):.4f}")
    print(f"  Min:  {np.min(confidences):.4f}")
    print(f"  Max:  {np.max(confidences):.4f}")

    # 정답/오답별 통계
    print(f"\n정답 샘플 ({len(correct_confidences)}개):")
    print(f"  Mean: {np.mean(correct_confidences):.4f}")
    print(f"  Std:  {np.std(correct_confidences):.4f}")

    print(f"\n오답 샘플 ({len(wrong_confidences)}개):")
    print(f"  Mean: {np.mean(wrong_confidences):.4f}")
    print(f"  Std:  {np.std(wrong_confidences):.4f}")

    # 임계값별 분포
    thresholds = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

    print(f"\n{'=' * 60}")
    print("임계값별 분포")
    print("=" * 60)
    print(f"{'임계값':<10} {'샘플 수':<12} {'비율':<10} {'정확도':<10}")
    print("-" * 42)

    for thresh in thresholds:
        mask = confidences >= thresh
        count = np.sum(mask)
        ratio = count / len(confidences) * 100

        # 해당 임계값 이상에서의 정확도
        if count > 0:
            correct_mask = np.array([c >= thresh for c in correct_confidences])
            acc = len(correct_confidences[correct_confidences >= thresh]) / count * 100
        else:
            acc = 0

        print(f">= {thresh:<7} {count:<12} {ratio:>6.1f}%    {acc:>6.1f}%")

    # 구간별 분포
    print(f"\n{'=' * 60}")
    print("구간별 분포 (Pattern A/B/C 설정 참고)")
    print("=" * 60)

    ranges = [
        (0.9, 1.0, "초고신뢰"),
        (0.8, 0.9, "고신뢰"),
        (0.7, 0.8, "중상신뢰"),
        (0.6, 0.7, "중신뢰"),
        (0.5, 0.6, "중하신뢰"),
        (0.4, 0.5, "저신뢰"),
        (0.0, 0.4, "초저신뢰"),
    ]

    print(f"{'구간':<15} {'샘플 수':<10} {'비율':<10} {'정확도':<10}")
    print("-" * 45)

    for low, high, name in ranges:
        mask = (confidences >= low) & (confidences < high)
        count = np.sum(mask)
        ratio = count / len(confidences) * 100

        # 해당 구간 정확도
        correct_in_range = np.sum((correct_confidences >= low) & (correct_confidences < high))
        acc = correct_in_range / count * 100 if count > 0 else 0

        print(f"{low:.1f}-{high:.1f} ({name:<4}) {count:<10} {ratio:>6.1f}%    {acc:>6.1f}%")

    # 권장 임계값
    print(f"\n{'=' * 60}")
    print("권장 임계값")
    print("=" * 60)

    # Pattern A: 정확도 90% 이상인 최저 임계값 찾기
    for thresh in [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6]:
        mask = confidences >= thresh
        count = np.sum(mask)
        if count > 0:
            correct_above = len(correct_confidences[correct_confidences >= thresh])
            acc = correct_above / count * 100
            if acc >= 90:
                pattern_a_thresh = thresh
                break
    else:
        pattern_a_thresh = 0.9

    # Pattern B: Pattern A 미만 ~ 0.5
    pattern_b_low = 0.5

    print(f"\nPattern A (고신뢰): confidence >= {pattern_a_thresh}")
    print(f"Pattern B (중신뢰): {pattern_b_low} <= confidence < {pattern_a_thresh}")
    print(f"Pattern C (저신뢰): confidence < {pattern_b_low}")

    # 권장 설정 적용 시 분포
    a_count = np.sum(confidences >= pattern_a_thresh)
    b_count = np.sum((confidences >= pattern_b_low) & (confidences < pattern_a_thresh))
    c_count = np.sum(confidences < pattern_b_low)

    print(f"\n권장 설정 적용 시:")
    print(f"  Pattern A: {a_count}개 ({a_count/len(confidences)*100:.1f}%)")
    print(f"  Pattern B: {b_count}개 ({b_count/len(confidences)*100:.1f}%)")
    print(f"  Pattern C: {c_count}개 ({c_count/len(confidences)*100:.1f}%)")

    # 파일 저장
    results = {
        'total_samples': len(confidences),
        'mean_confidence': float(np.mean(confidences)),
        'std_confidence': float(np.std(confidences)),
        'correct_mean': float(np.mean(correct_confidences)),
        'wrong_mean': float(np.mean(wrong_confidences)),
        'recommended_thresholds': {
            'pattern_a': pattern_a_thresh,
            'pattern_b_low': pattern_b_low
        }
    }

    output_path = Path(model_dir) / 'confidence_analysis.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n결과 저장: {output_path}")

if __name__ == '__main__':
    analyze_confidence()
