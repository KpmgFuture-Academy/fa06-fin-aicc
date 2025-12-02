# 모델 배치 안내

Final Classifier 모델 (LoRA 기반 KcELECTRA)은 다음 경로에 배치해야 합니다.

## 모델 배치 방법

### 모델 경로

모델 파일을 다음 위치에 배치:
```
models/final_classifier_model/model_final/
```

### 확인

```bash
ls models/final_classifier_model/model_final/
# best_model.pt, lora_adapter/ 등이 있어야 함
```

## 모델 파일 구조

배치 후 다음과 같은 구조여야 합니다:

```
models/final_classifier_model/
├── README.md                      # 모델 설명
└── model_final/
    ├── best_model.pt              # 최고 성능 체크포인트 (~500MB)
    ├── latest_checkpoint.pt       # 최신 체크포인트 (~500MB)
    ├── evaluation_results.txt     # 상세 평가 결과
    ├── confidence_analysis.json   # Confidence 분석 결과
    └── lora_adapter/              # LoRA 어댑터 (경량, 필수)
        ├── adapter_config.json    # 베이스 모델 정보 포함
        ├── adapter_model.safetensors (~4MB)
        └── README.md
```

**총 크기**: 약 500MB (LoRA 어댑터만 사용 시 ~4MB)

## 검증

모델이 정상적으로 배치되었는지 확인:

```bash
python -c "
import os
model_path = 'models/final_classifier_model/model_final'
lora_path = os.path.join(model_path, 'lora_adapter')

# 필수 파일 확인
required_files = [
    ('lora_adapter/adapter_config.json', lora_path),
    ('lora_adapter/adapter_model.safetensors', lora_path),
]

print('=== 필수 파일 (LoRA 어댑터) ===')
for name, base in required_files:
    file = name.split('/')[-1]
    path = os.path.join(base, file)
    if os.path.exists(path):
        size = os.path.getsize(path) / (1024**2)  # MB
        print(f'✓ {file}: {size:.1f} MB')
    else:
        print(f'✗ {file}: 누락')

# 선택 파일 확인
print('\n=== 선택 파일 (체크포인트) ===')
optional_files = ['best_model.pt', 'latest_checkpoint.pt']
for file in optional_files:
    path = os.path.join(model_path, file)
    if os.path.exists(path):
        size = os.path.getsize(path) / (1024**2)  # MB
        print(f'✓ {file}: {size:.1f} MB')
    else:
        print(f'- {file}: 없음 (선택사항)')
"
```

예상 출력:
```
=== 필수 파일 (LoRA 어댑터) ===
✓ adapter_config.json: 0.0 MB
✓ adapter_model.safetensors: 4.0 MB

=== 선택 파일 (체크포인트) ===
✓ best_model.pt: 500.0 MB
✓ latest_checkpoint.pt: 500.0 MB
```

## 문제 해결

### 모델을 찾을 수 없음

**증상**: 모델을 찾을 수 없다는 오류

**해결**:
```bash
# 현재 위치 확인
pwd

# 모델 경로 확인
ls models/final_classifier_model/model_final/

# 직접 경로 지정
python scripts/inference.py --model /절대/경로/models/final_classifier_model/model_final
```

### peft 라이브러리 오류

**증상**: `ModuleNotFoundError: No module named 'peft'`

**해결**:
```bash
pip install peft>=0.4.0
```

### 베이스 모델 다운로드 오류

**증상**: `beomi/KcELECTRA-base-v2022` 다운로드 실패

**해결**:
- 인터넷 연결 확인
- Hugging Face 접근 가능 여부 확인
- 오프라인 환경에서는 베이스 모델을 미리 다운로드 필요

## 모델 로드 방식

Final Classifier는 LoRA 방식으로 로드됩니다:

1. `adapter_config.json`에서 베이스 모델 정보 추출 (`beomi/KcELECTRA-base-v2022`)
2. 베이스 모델을 Hugging Face에서 다운로드 (첫 실행 시)
3. LoRA 어댑터 적용 (`lora_adapter/`)
4. (선택) `best_model.pt`에서 추가 가중치 및 라벨 매핑 로드

## 추가 정보

- **모델 버전**: v2.0.0 (Final Classifier with LoRA)
- **베이스 모델**: beomi/KcELECTRA-base-v2022
- **파인튜닝 방식**: LoRA (Low-Rank Adaptation)
- **카테고리**: 38개
- **도메인**: 8개

---

문제가 지속되면 프로젝트 관리자에게 문의하세요.
