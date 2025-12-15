"""Intent 분류 모델 LoRA Fine-tuning 스크립트

보강된 데이터를 사용하여 KcELECTRA 모델을 재학습합니다.

사용법:
    python scripts/finetune_intent_classifier.py --epochs 5
    python scripts/finetune_intent_classifier.py --augmented-data data/augmented_intent_training_data.json
"""

from __future__ import annotations

import json
import os
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
from tqdm import tqdm

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Transformers & PEFT
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    get_linear_schedule_with_warmup,
)
from peft import LoraConfig, get_peft_model, TaskType


# =============================================================================
# 설정
# =============================================================================

class Config:
    """학습 설정"""
    # 모델 설정
    BASE_MODEL = "beomi/KcELECTRA-base-v2022"
    NUM_LABELS = 38
    MAX_LENGTH = 128

    # LoRA 설정
    LORA_R = 8
    LORA_ALPHA = 16
    LORA_DROPOUT = 0.1
    LORA_TARGET_MODULES = ["query", "value"]

    # 학습 설정
    BATCH_SIZE = 16
    LEARNING_RATE = 2e-4
    EPOCHS = 5
    WARMUP_RATIO = 0.1
    WEIGHT_DECAY = 0.01

    # 경로
    MODEL_DIR = PROJECT_ROOT / "models" / "final_classifier_model" / "model_final"
    OUTPUT_DIR = PROJECT_ROOT / "models" / "final_classifier_model" / "model_retrained_v3"
    AUGMENTED_DATA_PATH = PROJECT_ROOT / "data" / "merged_training_data.json"

    # 시드
    SEED = 42


# =============================================================================
# 데이터셋 클래스
# =============================================================================

class IntentDataset(Dataset):
    """Intent 분류용 데이터셋"""

    def __init__(self, texts: List[str], labels: List[int], tokenizer, max_length: int):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt"
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(label, dtype=torch.long)
        }


# =============================================================================
# 데이터 로딩
# =============================================================================

def load_augmented_data(data_path: Path) -> Tuple[List[str], List[int]]:
    """보강된 데이터 로드"""
    print(f"\n[INFO] 보강 데이터 로드: {data_path}")

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = [item["text"] for item in data]
    labels = [item["intent_id"] for item in data]

    print(f"[OK] {len(texts):,}개 샘플 로드")

    return texts, labels


def load_id2intent(model_path: Path) -> Dict[int, str]:
    """id2intent 매핑 로드"""
    id2intent_path = model_path / "id2intent.json"

    if id2intent_path.exists():
        with open(id2intent_path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        return {int(k): v for k, v in mapping.items()}
    else:
        # 기본 매핑
        return {i: f"LABEL_{i}" for i in range(38)}


# =============================================================================
# 학습 함수
# =============================================================================

def set_seed(seed: int):
    """재현성을 위한 시드 설정"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def train_epoch(model, dataloader, optimizer, scheduler, device, epoch_num):
    """한 에폭 학습"""
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    pbar = tqdm(dataloader, desc=f"Epoch {epoch_num} Training", leave=True)
    for batch in pbar:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        optimizer.zero_grad()

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )

        loss = outputs.loss
        total_loss += loss.item()

        # 정확도 계산
        predictions = torch.argmax(outputs.logits, dim=-1)
        correct += (predictions == labels).sum().item()
        total += labels.size(0)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        # Progress bar 업데이트
        pbar.set_postfix({'loss': f'{loss.item():.4f}', 'acc': f'{correct/total:.4f}'})

    avg_loss = total_loss / len(dataloader)
    accuracy = correct / total

    return avg_loss, accuracy


def evaluate(model, dataloader, device):
    """평가"""
    model.eval()
    total_loss = 0
    all_predictions = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )

            total_loss += outputs.loss.item()
            predictions = torch.argmax(outputs.logits, dim=-1)

            all_predictions.extend(predictions.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    accuracy = accuracy_score(all_labels, all_predictions)
    f1_macro = f1_score(all_labels, all_predictions, average='macro')
    f1_weighted = f1_score(all_labels, all_predictions, average='weighted')

    return avg_loss, accuracy, f1_macro, f1_weighted, all_predictions, all_labels


# =============================================================================
# 메인 학습 로직
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Intent 분류기 LoRA Fine-tuning')
    parser.add_argument('--epochs', type=int, default=Config.EPOCHS, help='학습 에폭 수')
    parser.add_argument('--batch-size', type=int, default=Config.BATCH_SIZE, help='배치 크기')
    parser.add_argument('--lr', type=float, default=Config.LEARNING_RATE, help='학습률')
    parser.add_argument('--augmented-data', type=str, default=str(Config.AUGMENTED_DATA_PATH), help='보강 데이터 경로')
    parser.add_argument('--output-dir', type=str, default=str(Config.OUTPUT_DIR), help='출력 디렉토리')
    args = parser.parse_args()

    print("=" * 70)
    print("KcELECTRA LoRA Fine-tuning with Augmented Data")
    print("=" * 70)

    # 시드 설정
    set_seed(Config.SEED)

    # 디바이스 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n[INFO] 디바이스: {device}")
    if torch.cuda.is_available():
        print(f"[INFO] GPU: {torch.cuda.get_device_name(0)}")

    # 출력 디렉토리 생성
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ==========================================================================
    # 1. 데이터 로딩
    # ==========================================================================
    print("\n" + "=" * 70)
    print("[Step 1] 데이터 로딩")
    print("=" * 70)

    augmented_texts, augmented_labels = load_augmented_data(Path(args.augmented_data))
    id2intent = load_id2intent(Config.MODEL_DIR)

    # Train/Val 분할
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        augmented_texts, augmented_labels,
        test_size=0.2,
        random_state=Config.SEED,
        stratify=augmented_labels
    )

    print(f"[OK] 학습 데이터: {len(train_texts):,}개")
    print(f"[OK] 검증 데이터: {len(val_texts):,}개")

    # ==========================================================================
    # 2. 토크나이저 & 모델 로딩
    # ==========================================================================
    print("\n" + "=" * 70)
    print("[Step 2] 모델 로딩")
    print("=" * 70)

    tokenizer = AutoTokenizer.from_pretrained(Config.BASE_MODEL)
    print(f"[OK] 토크나이저 로드: {Config.BASE_MODEL}")

    # 베이스 모델 로드
    base_model = AutoModelForSequenceClassification.from_pretrained(
        Config.BASE_MODEL,
        num_labels=Config.NUM_LABELS,
        id2label=id2intent,
        label2id={v: k for k, v in id2intent.items()}
    )
    print(f"[OK] 베이스 모델 로드: {Config.BASE_MODEL}")

    # LoRA 설정
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=Config.LORA_R,
        lora_alpha=Config.LORA_ALPHA,
        lora_dropout=Config.LORA_DROPOUT,
        target_modules=Config.LORA_TARGET_MODULES,
    )

    model = get_peft_model(base_model, lora_config)
    model.to(device)

    # 학습 가능 파라미터 출력
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[OK] LoRA 적용: r={Config.LORA_R}, alpha={Config.LORA_ALPHA}")
    print(f"[OK] 학습 가능 파라미터: {trainable_params:,} / {total_params:,} ({100 * trainable_params / total_params:.2f}%)")

    # ==========================================================================
    # 3. 데이터셋 & 데이터로더
    # ==========================================================================
    print("\n" + "=" * 70)
    print("[Step 3] 데이터셋 준비")
    print("=" * 70)

    train_dataset = IntentDataset(train_texts, train_labels, tokenizer, Config.MAX_LENGTH)
    val_dataset = IntentDataset(val_texts, val_labels, tokenizer, Config.MAX_LENGTH)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    print(f"[OK] 학습 배치 수: {len(train_loader)}")
    print(f"[OK] 검증 배치 수: {len(val_loader)}")

    # ==========================================================================
    # 4. Optimizer & Scheduler
    # ==========================================================================
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=Config.WEIGHT_DECAY
    )

    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * Config.WARMUP_RATIO)

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps
    )

    print(f"[OK] 총 학습 스텝: {total_steps}")
    print(f"[OK] 웜업 스텝: {warmup_steps}")

    # ==========================================================================
    # 5. 학습 루프
    # ==========================================================================
    print("\n" + "=" * 70)
    print("[Step 4] 학습 시작")
    print("=" * 70)

    best_f1 = 0.0
    best_epoch = 0

    for epoch in range(args.epochs):
        print(f"\n[Epoch {epoch + 1}/{args.epochs}]")
        print("-" * 50)

        # 학습
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, scheduler, device, epoch + 1)
        print(f"  Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")

        # 평가
        val_loss, val_acc, val_f1_macro, val_f1_weighted, predictions, labels = evaluate(
            model, val_loader, device
        )
        print(f"  Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        print(f"  Val F1 (Macro): {val_f1_macro:.4f}, Val F1 (Weighted): {val_f1_weighted:.4f}")

        # 베스트 모델 저장
        if val_f1_macro > best_f1:
            best_f1 = val_f1_macro
            best_epoch = epoch + 1

            # 모델 저장
            model.save_pretrained(output_dir / "lora_adapter")
            tokenizer.save_pretrained(output_dir / "tokenizer")

            # 체크포인트 저장
            checkpoint = {
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "val_acc": val_acc,
                "val_f1_macro": val_f1_macro,
                "val_f1_weighted": val_f1_weighted,
                "label_mapping": {
                    "id2label": id2intent,
                    "label2id": {v: k for k, v in id2intent.items()}
                }
            }
            torch.save(checkpoint, output_dir / "best_model.pt")

            print(f"  [BEST] 모델 저장 (F1={val_f1_macro:.4f})")

    # ==========================================================================
    # 6. 최종 평가
    # ==========================================================================
    print("\n" + "=" * 70)
    print("[Step 5] 최종 평가")
    print("=" * 70)

    # 베스트 모델 로드
    best_checkpoint = torch.load(output_dir / "best_model.pt", map_location=device, weights_only=False)
    model.load_state_dict(best_checkpoint["model_state_dict"])

    val_loss, val_acc, val_f1_macro, val_f1_weighted, predictions, labels = evaluate(
        model, val_loader, device
    )

    # 분류 리포트 생성
    # 실제 존재하는 레이블만 사용
    unique_labels = sorted(set(labels) | set(predictions))
    intent_names = [id2intent.get(i, f"LABEL_{i}") for i in unique_labels]
    report = classification_report(
        labels, predictions,
        labels=unique_labels,
        target_names=intent_names,
        zero_division=0
    )

    print("\n[Classification Report]")
    print(report)

    # 결과 저장
    results = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "base_model": Config.BASE_MODEL,
            "lora_r": Config.LORA_R,
            "lora_alpha": Config.LORA_ALPHA,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
        },
        "data_stats": {
            "train_samples": len(train_texts),
            "val_samples": len(val_texts),
        },
        "best_metrics": {
            "epoch": best_epoch,
            "accuracy": val_acc,
            "f1_macro": val_f1_macro,
            "f1_weighted": val_f1_weighted,
        }
    }

    with open(output_dir / "training_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # id2intent 복사
    import shutil
    src_id2intent = Config.MODEL_DIR / "id2intent.json"
    if src_id2intent.exists():
        shutil.copy(src_id2intent, output_dir / "id2intent.json")

    print("\n" + "=" * 70)
    print("[완료] 학습 완료!")
    print("=" * 70)
    print(f"  Best Epoch: {best_epoch}")
    print(f"  Accuracy: {val_acc:.4f}")
    print(f"  F1 (Macro): {val_f1_macro:.4f}")
    print(f"  F1 (Weighted): {val_f1_weighted:.4f}")
    print(f"  모델 저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
