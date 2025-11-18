"""
BERT 모델 평가
학습된 모델로 예측 및 성능 분석

사용법:
    # 기본 사용 (자동 경로 탐색)
    python evaluate.py

    # 커스텀 경로 지정
    python evaluate.py --model /path/to/model --data /path/to/val.csv
"""

import json
import os
import sys
import argparse
import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# 한글 폰트 설정 (한국어 시각화용)
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass  # 폰트 없으면 기본 폰트 사용


def find_model_path():
    """모델 경로 자동 탐색"""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '../models/bert_intent_classifier'),
        os.path.join(os.getcwd(), 'models/bert_intent_classifier'),
        os.path.join(os.getcwd(), '../models/bert_intent_classifier'),
    ]

    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)

    return None


def find_data_path():
    """검증 데이터 경로 자동 탐색"""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/processed/val.csv'),
        os.path.join(os.getcwd(), 'data/processed/val.csv'),
        os.path.join(os.getcwd(), '../data/processed/val.csv'),
    ]

    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)

    return None


def predict(text, model, tokenizer, id2intent, device, top_k=1):
    """텍스트 의도 예측"""
    inputs = tokenizer(
        text,
        return_tensors='pt',
        max_length=128,
        padding='max_length',
        truncation=True
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)

    top_probs, top_indices = torch.topk(probabilities[0], k=top_k)

    results = []
    for prob, idx in zip(top_probs, top_indices):
        results.append({
            'intent': id2intent[idx.item()],
            'confidence': prob.item()
        })

    return results


def main():
    # 인자 파싱
    parser = argparse.ArgumentParser(description='BERT 모델 평가')
    parser.add_argument('--model', type=str, default=None, help='모델 경로 (기본: 자동 탐색)')
    parser.add_argument('--data', type=str, default=None, help='검증 데이터 경로 (기본: 자동 탐색)')
    parser.add_argument('--output', type=str, default='outputs', help='결과 저장 디렉토리 (기본: outputs)')
    parser.add_argument('--sample-size', type=int, default=None, help='평가 샘플 수 제한 (테스트용)')
    args = parser.parse_args()

    # 디바이스 설정
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n사용 디바이스: {device}")

    # ========================================================================
    # Step 1: 모델 로드
    # ========================================================================

    print("\n" + "=" * 80)
    print("BERT 모델 평가")
    print("=" * 80)

    # 모델 경로 찾기
    model_path = args.model if args.model else find_model_path()

    if not model_path or not os.path.exists(model_path):
        print(f"\n[ERROR] 모델을 찾을 수 없습니다.")
        print(f"  시도한 경로: {model_path}")
        print(f"\n해결 방법:")
        print(f"  1. 모델 다운로드: MODEL_DOWNLOAD.md 참조")
        print(f"  2. --model 옵션으로 경로 지정")
        sys.exit(1)

    print(f"\n[INFO] 모델 로드 중: {model_path}")

    # 모델 로드
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()

    # 라벨 매핑 로드
    with open(f'{model_path}/id2intent.json', 'r', encoding='utf-8') as f:
        id2intent = json.load(f)
        id2intent = {int(k): v for k, v in id2intent.items()}

    print(f"[OK] 모델 로드 완료")
    print(f"  - 의도 종류: {len(id2intent):,}개")

    # ========================================================================
    # Step 2: 검증 데이터 로드
    # ========================================================================

    # 데이터 경로 찾기
    data_path = args.data if args.data else find_data_path()

    if not data_path or not os.path.exists(data_path):
        print(f"\n[WARNING] 검증 데이터를 찾을 수 없습니다: {data_path}")
        print(f"  샘플 데이터로만 테스트를 진행합니다.")
        run_sample_test(model, tokenizer, id2intent, device)
        sys.exit(0)

    print(f"\n[INFO] 데이터 로드 중: {data_path}")
    val_df = pd.read_csv(data_path)

    # 샘플 크기 제한
    if args.sample_size:
        val_df = val_df.head(args.sample_size)
        print(f"[INFO] 샘플 크기 제한: {args.sample_size}개")

    print(f"[OK] 평가 샘플 수: {len(val_df):,}개")

    # ========================================================================
    # Step 3: 예측 및 평가
    # ========================================================================

    print("\n" + "=" * 80)
    print("예측 진행 중...")
    print("=" * 80)

    predictions = []
    true_labels = []

    for idx, row in val_df.iterrows():
        if idx % 100 == 0 and idx > 0:
            print(f"  진행: {idx}/{len(val_df)} ({idx/len(val_df)*100:.1f}%)")

        text = row['text']
        true_intent = row['intent']

        # 예측
        results = predict(text, model, tokenizer, id2intent, device, top_k=1)
        pred_intent = results[0]['intent']

        predictions.append(pred_intent)
        true_labels.append(true_intent)

    print(f"[OK] 예측 완료: {len(predictions):,}개")

    # ========================================================================
    # Step 4: 성능 평가
    # ========================================================================

    print("\n" + "=" * 80)
    print("성능 평가 결과")
    print("=" * 80)

    # 정확도
    accuracy = accuracy_score(true_labels, predictions)
    print(f"\n전체 정확도: {accuracy:.4f} ({accuracy*100:.2f}%)")

    # Classification Report
    print("\nClassification Report (샘플):")
    print(classification_report(true_labels, predictions, zero_division=0, labels=list(set(true_labels))[:10]))

    # ========================================================================
    # Step 5: 오분류 분석
    # ========================================================================

    print("\n" + "=" * 80)
    print("오분류 분석 (상위 10개)")
    print("=" * 80)

    misclassified = []
    for i, (true, pred) in enumerate(zip(true_labels, predictions)):
        if true != pred:
            misclassified.append({
                'text': val_df.iloc[i]['text'],
                'true_intent': true,
                'pred_intent': pred
            })

    print(f"\n총 오분류 샘플: {len(misclassified):,}개 ({len(misclassified)/len(val_df)*100:.2f}%)")

    # 상위 10개 출력
    print("\n오분류 예시:")
    for i, item in enumerate(misclassified[:10], 1):
        print(f"\n{i}. 텍스트: {item['text'][:60]}...")
        print(f"   실제 의도: {item['true_intent']}")
        print(f"   예측 의도: {item['pred_intent']}")

    # ========================================================================
    # Step 6: 결과 저장
    # ========================================================================

    # 출력 디렉토리 생성
    os.makedirs(args.output, exist_ok=True)

    # 오분류 저장
    if misclassified:
        misclassified_df = pd.DataFrame(misclassified)
        output_file = os.path.join(args.output, 'misclassified.csv')
        misclassified_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 오분류 데이터 저장: {output_file}")

    # 평가 결과 저장
    eval_results = {
        'accuracy': float(accuracy),
        'total_samples': len(val_df),
        'misclassified': len(misclassified),
        'model_path': model_path,
        'data_path': data_path
    }

    results_file = os.path.join(args.output, 'evaluation_results.json')
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)

    print(f"[OK] 평가 결과 저장: {results_file}")

    print("\n" + "=" * 80)
    print("평가 완료!")
    print("=" * 80)


def run_sample_test(model, tokenizer, id2intent, device):
    """샘플 데이터로 테스트 (데이터 파일이 없을 때)"""
    print("\n" + "=" * 80)
    print("샘플 테스트")
    print("=" * 80)

    test_queries = [
        "신용카드를 발급하고 싶어요",
        "보험 청구하려고 하는데요",
        "계좌 이체를 어떻게 하나요?",
        "대출 상담 받고 싶습니다",
        "잔고 조회 부탁드려요",
        "비밀번호를 잊어버렸어요",
    ]

    for query in test_queries:
        results = predict(query, model, tokenizer, id2intent, device, top_k=3)

        print(f"\n질문: {query}")
        print("  예측 결과:")
        for i, result in enumerate(results, 1):
            print(f"    {i}. {result['intent']:30s} ({result['confidence']:.2%})")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
