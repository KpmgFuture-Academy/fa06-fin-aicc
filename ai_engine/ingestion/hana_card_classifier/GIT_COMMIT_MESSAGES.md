# 추천 Git 커밋 메시지

GitHub 업로드 시 사용할 수 있는 커밋 메시지 템플릿입니다.

---

## 1. 초기 커밋 (전체 업로드)

### 옵션 A: 간결한 버전
```
feat: Hana Card NLU Category Pipeline v3.0.0 초기 릴리스

- Electra 기반 카테고리 분류 파이프라인
- Clarification Loop (최대 3회 재질문)
- LLM Refine 후처리
- LangGraph 기반 파이프라인 구성
```

### 옵션 B: 상세 버전 (권장)
```
feat: Hana Card NLU Category Pipeline v3.0.0 초기 릴리스

## 핵심 기능
- Electra 기반 카테고리 자동 분류 (Temperature Scaling T=0.1)
- Confidence Pattern (A/B/C) 기반 라우팅
- Clarification Loop: 저신뢰 분류 시 최대 3회 재질문
- LLM Refine: 최대 횟수 도달 시 Claude API로 최종 결정
- LangGraph 기반 파이프라인 오케스트레이션

## 주요 모듈
- nlu_category/: 핵심 파이프라인 패키지
- examples/: 테스트 스크립트
- scripts/: 실행 스크립트 (Windows/Linux)

## Confidence Threshold
- Pattern A (≥10%): 고신뢰 → 바로 최종 분류
- Pattern B (5-10%): 중신뢰 → Clarification Loop
- Pattern C (<5%): 저신뢰 → Clarification Loop

Note: 모델 파일은 용량 문제로 별도 배포 (Google Drive)
```

---

## 2. 모듈별 커밋 (분할 업로드 시)

### 2.1 Core 모듈
```
feat(nlu_category): 핵심 파이프라인 모듈 추가

- types.py: 타입 정의 (TypedDict, Enum)
- state.py: 파이프라인 상태 관리
- config.py: 설정 파일
- prompts.py: 프롬프트 템플릿
```

### 2.2 Node 모듈
```
feat(nodes): 파이프라인 노드 모듈 추가

- nodes_preprocess.py: 텍스트 전처리
- nodes_category.py: Electra 카테고리 분류
- nodes_confidence.py: Confidence 패턴 결정 (A/B/C)
- nodes_rag.py: RAG 검색
- nodes_llm.py: LLM 응답 생성
```

### 2.3 Clarification Loop
```
feat(clarify): Clarification Loop 구현 (v3)

- conversation_utils.py: 대화 이력 관리, effective_query 생성
- llm_clarify.py: 재질문 생성 서비스 (Mock/Claude)
- 최대 3회 재질문 후 LLM Refine으로 전환
- Pattern A 도달 시 조기 종료
```

### 2.4 LLM Refine
```
feat(refine): LLM Refine 서비스 추가

- llm_refine.py: top3 후보 중 최종 카테고리 선택
- refine_from_conversation(): Conversation 객체 기반 Refine
- Mock/Claude 모드 지원
```

### 2.5 Graph Builder
```
feat(graph): LangGraph 파이프라인 빌더

- graph_builder.py: 전체 파이프라인 구성
- run_clarification_loop(): Clarification 루프 실행
- final_classification_node(): 최종 분류 확정
```

### 2.6 테스트 & 스크립트
```
feat(examples): 테스트 스크립트 추가

- test_llm_refine_pipeline.py: 전체 파이프라인 테스트
- test_clarify_only.py: Clarification 단독 테스트
- test_refine_only.py: LLM Refine 단독 테스트
- scripts/run_tests.bat, run_tests.sh: 실행 스크립트
```

### 2.7 문서
```
docs: README 및 파이프라인 문서 추가

- README.md: 프로젝트 소개, 설치 방법, 사용법
- nlu_category/docs/pipeline_overview.md: 상세 구조 문서
- requirements.txt: 의존성 패키지 목록
```

---

## 3. 버그 수정 / 기능 개선 시

### 버그 수정
```
fix(confidence): Pattern B 임계값 수정

- 기존: 0.03 (3%)
- 변경: 0.05 (5%)
- 테스트 케이스 통과 확인
```

### 기능 개선
```
perf(electra): Temperature Scaling 최적화

- T=0.2 → T=0.1 변경
- 확률 분포 sharpness 개선
- 고신뢰 분류 비율 15% 증가
```

### 리팩토링
```
refactor(clarify): Clarification 서비스 인터페이스 개선

- LLMClarifier Protocol 추가
- Mock/Claude clarifier 분리
- 테스트 용이성 향상
```

---

## 4. 태그 (릴리스)

```bash
git tag -a v3.0.0 -m "Hana Card NLU Pipeline v3.0.0 - Clarification Loop"
git push origin v3.0.0
```

---

## 커밋 메시지 컨벤션

| 타입 | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `style` | 코드 포맷팅 (기능 변경 없음) |
| `refactor` | 리팩토링 |
| `perf` | 성능 개선 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 설정 파일 변경 |
