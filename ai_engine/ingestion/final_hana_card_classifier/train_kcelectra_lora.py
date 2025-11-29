"""
KcELECTRA LoRA Fine-tuning 스크립트
- 모델: beomi/KcELECTRA-base-v2022
- 방식: LoRA (Low-Rank Adaptation) - 인코더 일부 학습
- PEFT 라이브러리 사용
- 8GB VRAM 최적화
"""
import os
import json
import argparse
from pathlib import Path
import time

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    ElectraTokenizer,
    ElectraForSequenceClassification,
    get_linear_schedule_with_warmup
)
from peft import LoraConfig, get_peft_model, TaskType
from sklearn.metrics import accuracy_score, f1_score, classification_report
from tqdm import tqdm


class ConsultingDataset(Dataset):
    """상담 데이터셋"""

    def __init__(self, data_dir: Path, tokenizer, label2id: dict, max_length: int = 512):
        self.tokenizer = tokenizer
        self.label2id = label2id
        self.max_length = max_length
        self.samples = []

        # 데이터 로드
        for root, dirs, files in os.walk(data_dir):
            for filename in files:
                if not filename.endswith('.json'):
                    continue

                filepath = Path(root) / filename
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    text = data[0].get('consulting_content', '')
                    category = data[0].get('consulting_category', '').strip()

                    if not text or not category:
                        continue
                    if category not in label2id:
                        continue

                    self.samples.append({
                        'text': text,
                        'label': label2id[category]
                    })
                except:
                    continue

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]

        encoding = self.tokenizer(
            sample['text'],
            truncation=True,
            max_length=self.max_length,
            padding='max_length',
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'label': torch.tensor(sample['label'], dtype=torch.long)
        }


def load_categories(category_file: Path) -> dict:
    """카테고리 파일 로드"""
    label2id = {}
    id2label = {}

    with open(category_file, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[0].isdigit():
                category = parts[1]
            else:
                category = line

            label2id[category] = idx
            id2label[idx] = category

    return label2id, id2label


def train_epoch(model, dataloader, optimizer, scheduler, device):
    """한 에포크 학습"""
    model.train()
    total_loss = 0
    all_preds = []
    all_labels = []

    pbar = tqdm(dataloader, desc="Training")
    for batch in pbar:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['label'].to(device)

        optimizer.zero_grad()

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )

        loss = outputs.loss
        loss.backward()

        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

        preds = torch.argmax(outputs.logits, dim=1)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())

        pbar.set_postfix({'loss': f'{loss.item():.4f}'})

    avg_loss = total_loss / len(dataloader)
    accuracy = accuracy_score(all_labels, all_preds)

    return avg_loss, accuracy


def evaluate(model, dataloader, device, id2label=None):
    """평가"""
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['label'].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )

            total_loss += outputs.loss.item()

            preds = torch.argmax(outputs.logits, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    accuracy = accuracy_score(all_labels, all_preds)
    macro_f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)
    weighted_f1 = f1_score(all_labels, all_preds, average='weighted', zero_division=0)

    return {
        'loss': avg_loss,
        'accuracy': accuracy,
        'macro_f1': macro_f1,
        'weighted_f1': weighted_f1,
        'preds': all_preds,
        'labels': all_labels
    }


def main():
    parser = argparse.ArgumentParser(description='KcELECTRA LoRA Fine-tuning')
    parser.add_argument('--model_name', type=str, default='beomi/KcELECTRA-base-v2022')
    parser.add_argument('--train_dir', type=str, required=True)
    parser.add_argument('--val_dir', type=str, required=True)
    parser.add_argument('--category_file', type=str, required=True)
    parser.add_argument('--output_dir', type=str, default='./outputs/kcelectra_lora')
    parser.add_argument('--max_length', type=int, default=512)
    parser.add_argument('--batch_size', type=int, default=8)  # LoRA는 배치 사이즈 작게
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--learning_rate', type=float, default=2e-4)  # LoRA 권장 LR
    parser.add_argument('--warmup_ratio', type=float, default=0.1)
    # LoRA 설정
    parser.add_argument('--lora_r', type=int, default=8, help='LoRA rank')
    parser.add_argument('--lora_alpha', type=int, default=16, help='LoRA alpha')
    parser.add_argument('--lora_dropout', type=float, default=0.1)
    parser.add_argument('--resume', type=str, default=None)
    args = parser.parse_args()

    # 디바이스 설정
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")

    # 출력 디렉토리 생성
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 카테고리 로드
    print(f"\n카테고리 로드: {args.category_file}")
    label2id, id2label = load_categories(Path(args.category_file))
    num_labels = len(label2id)
    print(f"카테고리 수: {num_labels}")

    # 토크나이저 로드
    print(f"\n토크나이저 로드: {args.model_name}")
    tokenizer = ElectraTokenizer.from_pretrained(args.model_name)

    # 데이터셋 로드
    print(f"\n학습 데이터 로드: {args.train_dir}")
    train_dataset = ConsultingDataset(
        Path(args.train_dir), tokenizer, label2id, args.max_length
    )
    print(f"학습 샘플 수: {len(train_dataset):,}")

    print(f"\n검증 데이터 로드: {args.val_dir}")
    val_dataset = ConsultingDataset(
        Path(args.val_dir), tokenizer, label2id, args.max_length
    )
    print(f"검증 샘플 수: {len(val_dataset):,}")

    # 데이터로더
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0
    )

    # 모델 로드 (HuggingFace Sequence Classification)
    print(f"\n모델 로드: {args.model_name}")
    model = ElectraForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id
    )

    # LoRA 설정
    print(f"\nLoRA 설정 적용...")
    print(f"  - rank (r): {args.lora_r}")
    print(f"  - alpha: {args.lora_alpha}")
    print(f"  - dropout: {args.lora_dropout}")

    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["query", "key", "value"],  # Attention 레이어에 LoRA 적용
        bias="none",
    )

    model = get_peft_model(model, lora_config)
    model.to(device)

    # 학습 가능한 파라미터 수 확인
    model.print_trainable_parameters()

    # 옵티마이저 & 스케줄러
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=0.01
    )

    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)

    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    # 체크포인트에서 재개
    start_epoch = 0
    best_val_f1 = 0

    if args.resume and os.path.exists(args.resume):
        print(f"\n체크포인트 로드: {args.resume}")
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        if 'scheduler_state_dict' in checkpoint:
            scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        start_epoch = checkpoint.get('epoch', 0) + 1
        best_val_f1 = checkpoint.get('val_weighted_f1', 0)
        print(f"에포크 {start_epoch}부터 재개 (Best F1: {best_val_f1:.4f})")

    # 학습
    print(f"\n{'='*60}")
    print(f"LoRA Fine-tuning 시작")
    print(f"{'='*60}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Total steps: {total_steps:,}")
    print(f"Warmup steps: {warmup_steps:,}")

    start_time = time.time()

    for epoch in range(start_epoch, args.epochs):
        print(f"\n--- Epoch {epoch+1}/{args.epochs} ---")

        # 학습
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, scheduler, device
        )
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")

        # 검증
        val_results = evaluate(model, val_loader, device, id2label)
        print(f"Val Loss: {val_results['loss']:.4f}")
        print(f"Val Accuracy: {val_results['accuracy']:.4f}")
        print(f"Val Macro F1: {val_results['macro_f1']:.4f}")
        print(f"Val Weighted F1: {val_results['weighted_f1']:.4f}")

        # 매 에포크마다 체크포인트 저장
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict(),
            'val_accuracy': val_results['accuracy'],
            'val_macro_f1': val_results['macro_f1'],
            'val_weighted_f1': val_results['weighted_f1'],
            'best_val_f1': best_val_f1,
        }, output_dir / 'latest_checkpoint.pt')
        print(f">> Latest checkpoint saved (epoch {epoch+1})")

        # 베스트 모델 저장
        if val_results['weighted_f1'] > best_val_f1:
            best_val_f1 = val_results['weighted_f1']
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'val_accuracy': val_results['accuracy'],
                'val_macro_f1': val_results['macro_f1'],
                'val_weighted_f1': val_results['weighted_f1'],
            }, output_dir / 'best_model.pt')

            # LoRA 어댑터만 별도 저장 (경량화)
            model.save_pretrained(output_dir / 'lora_adapter')
            print(f">> Best model saved! (Weighted F1: {best_val_f1:.4f})")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"학습 완료!")
    print(f"{'='*60}")
    print(f"총 소요 시간: {elapsed/60:.1f}분")
    print(f"Best Weighted F1: {best_val_f1:.4f}")

    # 최종 평가 및 리포트 저장
    print(f"\n최종 평가 리포트 생성...")

    # 베스트 모델 로드
    checkpoint = torch.load(output_dir / 'best_model.pt', weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])

    final_results = evaluate(model, val_loader, device, id2label)

    # Classification Report
    unique_labels = sorted(set(final_results['labels']) | set(final_results['preds']))
    target_names = [id2label[i] for i in unique_labels]
    report = classification_report(
        final_results['labels'], final_results['preds'],
        labels=unique_labels, target_names=target_names, zero_division=0
    )

    # 결과 저장
    result_file = output_dir / 'evaluation_results.txt'
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("KcELECTRA LoRA Fine-tuning 평가 결과\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"모델: {args.model_name}\n")
        f.write(f"LoRA rank: {args.lora_r}\n")
        f.write(f"LoRA alpha: {args.lora_alpha}\n")
        f.write(f"학습 데이터: {len(train_dataset):,}개\n")
        f.write(f"검증 데이터: {len(val_dataset):,}개\n")
        f.write(f"카테고리 수: {num_labels}개\n")
        f.write(f"Epochs: {args.epochs}\n")
        f.write(f"Batch size: {args.batch_size}\n")
        f.write(f"Learning rate: {args.learning_rate}\n\n")
        f.write(f"Accuracy: {final_results['accuracy']:.4f}\n")
        f.write(f"Macro F1: {final_results['macro_f1']:.4f}\n")
        f.write(f"Weighted F1: {final_results['weighted_f1']:.4f}\n\n")
        f.write("Classification Report:\n")
        f.write(report)

    print(f"결과 저장: {result_file}")
    print(f"\n{report}")


if __name__ == '__main__':
    main()
