# 폴더 정리 계획표 (파일 매핑 테이블)
## Hana_Card → Hana_Card_GitHub 파일 매핑

---

## 1. 루트 파일

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **새로 생성** | - | `README.md` | GitHub용 프로젝트 소개 |
| **새로 생성** | - | `requirements.txt` | 의존성 패키지 목록 |
| **복사** | `nlu_category/test_samples/test_queries.txt` | `test_queries.txt` | 테스트 쿼리 파일 |
| **새로 생성** | - | `.gitignore` | Git 무시 파일 |

---

## 2. nlu_category/ 핵심 모듈

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **복사** | `nlu_category/__init__.py` | `nlu_category/__init__.py` | 패키지 초기화 (v3.0.0) |
| **복사** | `nlu_category/types.py` | `nlu_category/types.py` | 타입 정의 |
| **복사** | `nlu_category/state.py` | `nlu_category/state.py` | 파이프라인 상태 |
| **복사** | `nlu_category/config.py` | `nlu_category/config.py` | 설정 파일 |
| **복사** | `nlu_category/prompts.py` | `nlu_category/prompts.py` | 프롬프트 템플릿 |

---

## 3. nlu_category/ 노드 모듈

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **복사** | `nlu_category/nodes_preprocess.py` | `nlu_category/nodes_preprocess.py` | 전처리 노드 |
| **복사** | `nlu_category/nodes_category.py` | `nlu_category/nodes_category.py` | 카테고리 분류 노드 |
| **복사** | `nlu_category/nodes_confidence.py` | `nlu_category/nodes_confidence.py` | Confidence 결정 노드 (v3) |
| **복사** | `nlu_category/nodes_rag.py` | `nlu_category/nodes_rag.py` | RAG 노드 |
| **복사** | `nlu_category/nodes_llm.py` | `nlu_category/nodes_llm.py` | LLM 응답 노드 (v3) |

---

## 4. nlu_category/ 서비스 모듈

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **복사** | `nlu_category/model_service_electra.py` | `nlu_category/model_service_electra.py` | Electra 모델 서비스 |
| **복사** | `nlu_category/conversation_utils.py` | `nlu_category/conversation_utils.py` | 대화 유틸 (v3) |
| **복사** | `nlu_category/llm_clarify.py` | `nlu_category/llm_clarify.py` | Clarification 서비스 (v3) |
| **복사** | `nlu_category/llm_refine.py` | `nlu_category/llm_refine.py` | LLM Refine 서비스 (v3) |
| **복사** | `nlu_category/graph_builder.py` | `nlu_category/graph_builder.py` | LangGraph 빌더 (v3) |

---

## 5. nlu_category/utils/ 유틸리티 (새로 생성)

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **새로 생성** | - | `nlu_category/utils/__init__.py` | 유틸 패키지 초기화 |
| **새로 생성** | - | `nlu_category/utils/logger.py` | 로깅 유틸리티 |
| **새로 생성** | - | `nlu_category/utils/text_normalizer.py` | 텍스트 정규화 |

---

## 6. nlu_category/docs/ 문서 (새로 생성)

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **새로 생성** | - | `nlu_category/docs/pipeline_overview.md` | 파이프라인 구조 문서 |

---

## 7. examples/ 테스트 예제

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **복사** | `examples/test_llm_refine_pipeline.py` | `examples/test_llm_refine_pipeline.py` | 전체 파이프라인 테스트 (v3) |
| **새로 생성** | - | `examples/test_clarify_only.py` | Clarification Loop 단독 테스트 |
| **새로 생성** | - | `examples/test_refine_only.py` | LLM Refine 단독 테스트 |

---

## 8. scripts/ 실행 스크립트 (새로 생성)

| 상태 | 원본 위치 | 대상 위치 | 비고 |
|------|----------|----------|------|
| **새로 생성** | - | `scripts/run_tests.bat` | Windows 테스트 실행 |
| **새로 생성** | - | `scripts/run_tests.sh` | Linux/Mac 테스트 실행 |

---

## 9. 제외 항목 (GitHub에 포함하지 않음)

| 제외 항목 | 사유 |
|----------|------|
| `models/` | 용량 문제 - Google Drive로 별도 배포 |
| `data/` | 원본 데이터 - 보안/용량 문제 |
| `scripts/*.py` (학습 스크립트) | 학습용 스크립트 불필요 |
| `__pycache__/` | 캐시 파일 |
| `*.pyc` | 컴파일된 파이썬 파일 |
| `tests/` | 기존 테스트 (examples로 대체) |

---

## 요약

| 구분 | 개수 |
|------|------|
| 복사할 파일 | 15개 |
| 새로 생성할 파일 | 12개 |
| 총 파일 수 | 27개 |
| 총 폴더 수 | 5개 (`nlu_category`, `nlu_category/utils`, `nlu_category/docs`, `examples`, `scripts`) |
