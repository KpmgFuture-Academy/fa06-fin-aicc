# 모델 다운로드 안내

학습된 BERT 모델 파일은 용량 제한으로 Git 저장소에 포함되지 않습니다 (435MB).

## 다운로드 방법

### Option 1: Google Drive (권장)

1. **다운로드 링크**:
   [Google Drive에서 다운로드](https://drive.google.com/drive/folders/14HhWnQG5GJjZi_9XMdPs6Vl8H-eUcuSf)

2. **압축 해제**:
   ```bash
   # 다운로드한 파일 압축 해제
   unzip bert_intent_classifier.zip -d models/
   ```

3. **확인**:
   ```bash
   ls models/bert_intent_classifier/
   # model.safetensors, config.json 등이 있어야 함
   ```

### Option 2: Hugging Face Hub

```bash
# Hugging Face CLI 설치
pip install huggingface-hub

# 모델 다운로드 (업로드 후 사용 가능)
huggingface-cli download your-username/bert-financial-intent \
  --local-dir models/bert_intent_classifier
```

### Option 3: 직접 전달

팀 내부 공유 서버나 네트워크 드라이브에서 다운로드:
```
\\shared-drive\models\bert_intent_classifier\
```

## 모델 파일 구조

다운로드 후 다음과 같은 구조여야 합니다:

```
models/bert_intent_classifier/
├── model.safetensors          # 433MB (모델 가중치)
├── config.json                # 모델 설정
├── id2intent.json             # ID → 의도 매핑
├── intent2id.json             # 의도 → ID 매핑
├── tokenizer.json             # 토크나이저
├── tokenizer_config.json
├── special_tokens_map.json
├── vocab.txt                  # 어휘 사전
└── training_args.bin          # 학습 인자
```

**총 크기**: 약 435MB

## 검증

모델이 정상적으로 다운로드되었는지 확인:

```bash
python -c "
import os
model_path = 'models/bert_intent_classifier'
required_files = ['model.safetensors', 'config.json', 'id2intent.json']

for file in required_files:
    path = os.path.join(model_path, file)
    if os.path.exists(path):
        size = os.path.getsize(path) / (1024**2)  # MB
        print(f'✓ {file}: {size:.1f} MB')
    else:
        print(f'✗ {file}: 누락')
"
```

예상 출력:
```
✓ model.safetensors: 433.0 MB
✓ config.json: 0.2 MB
✓ id2intent.json: 0.1 MB
```

## 문제 해결

### 다운로드 실패

**증상**: 파일 다운로드가 중단되거나 실패

**해결**:
- 인터넷 연결 확인
- 충분한 디스크 공간 확보 (최소 500MB)
- 브라우저 대신 다운로드 관리자 사용

### 압축 해제 오류

**증상**: 압축 파일이 손상됨

**해결**:
- 파일 크기 확인 (약 400MB여야 함)
- 재다운로드
- 다른 압축 해제 도구 사용 (7-Zip 등)

### 경로 오류

**증상**: 모델을 찾을 수 없다는 오류

**해결**:
```bash
# 현재 위치 확인
pwd

# 모델 경로 확인
ls models/bert_intent_classifier/

# 직접 경로 지정
python scripts/inference.py --model /절대/경로/models/bert_intent_classifier
```

## 네트워크 제한 환경

회사 방화벽 등으로 외부 다운로드가 불가능한 경우:

1. **USB 드라이브 사용**:
   - 외부에서 다운로드 후 USB로 전달

2. **내부 서버 활용**:
   - IT 부서에 요청하여 내부 서버에 업로드

3. **오프라인 패키지**:
   - 모든 파일을 압축하여 전달

## 추가 정보

- **모델 버전**: v1.0.0 (2025-11-18)
- **파일 형식**: SafeTensors (PyTorch 호환)
- **체크섬**: [여기에 MD5/SHA256 체크섬 추가]

---

문제가 지속되면 프로젝트 관리자에게 문의하세요.
