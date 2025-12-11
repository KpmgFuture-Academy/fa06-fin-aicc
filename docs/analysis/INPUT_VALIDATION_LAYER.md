# 입력 검증 레이어 (Input Validation Layer)

## 개요

LangGraph 워크플로우 진입 전에 사용자 입력을 검증하여 시스템 안정성을 보장하는 외부 검증 레이어입니다.

## 변경 이력

| 날짜 | 변경 내용 | 파일 |
|------|----------|------|
| 2025-12-09 | 입력 검증 레이어 추가 | `app/services/workflow_service.py` |

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                          │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           External Validation Layer                      │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  validate_input()                                │    │   │
│  │  │  - 빈 입력 검증 (2자 미만)                        │    │   │
│  │  │  - 매우 긴 입력 검증 (2000자 초과)                │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │                         │                                │   │
│  │         ┌───────────────┼───────────────┐               │   │
│  │         ▼               │               ▼               │   │
│  │   [검증 실패]           │        [검증 통과]            │   │
│  │   즉시 응답 반환        │                               │   │
│  └─────────────────────────│───────────────────────────────┘   │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           LangGraph Workflow                             │   │
│  │  triage_agent → answer_agent → chat_db_storage          │   │
│  │                                                          │   │
│  │  내부 처리:                                              │   │
│  │  - RAG 실패 fallback                                    │   │
│  │  - Intent 분류 실패 fallback                            │   │
│  │  - LLM API 오류 (timeout, connection, quota)            │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 검증 항목

### 1. 빈 입력 검증
- **조건**: `None`, 빈 문자열, 공백만 있는 문자열, 2자 미만
- **응답 메시지**: "메시지를 입력해 주세요."
- **error_type**: `"empty"`

### 2. 매우 긴 입력 검증
- **조건**: 2000자 초과
- **응답 메시지**: "입력이 너무 깁니다. 2000자 이하로 입력해 주세요. (현재: N자)"
- **error_type**: `"too_long"`

## 설정 상수

```python
MIN_INPUT_LENGTH = 2       # 최소 입력 길이
MAX_INPUT_LENGTH = 2000    # 최대 입력 길이
```

## 코드 구조

### ValidationResult (데이터 클래스)

```python
@dataclass
class ValidationResult:
    """입력 검증 결과"""
    is_valid: bool
    error_type: Optional[str] = None  # "empty", "too_long", None
    error_message: Optional[str] = None
```

### validate_input() 함수

```python
def validate_input(user_message: str) -> ValidationResult:
    """
    사용자 입력 검증 (LangGraph 워크플로우 진입 전 외부 검증)

    Returns:
        ValidationResult: 검증 결과
    """
```

### create_validation_error_response() 함수

```python
def create_validation_error_response(validation_result: ValidationResult) -> ChatResponse:
    """
    검증 실패 시 즉시 반환할 ChatResponse 생성
    """
```

## 처리 흐름

```python
async def process_chat_message(request: ChatRequest) -> ChatResponse:
    # Step 1: 입력 검증 (External Validation Layer)
    validation_result = validate_input(request.user_message)

    if not validation_result.is_valid:
        # 검증 실패 시 LangGraph 워크플로우를 실행하지 않고 즉시 응답 반환
        return create_validation_error_response(validation_result)

    # Step 2: LangGraph 워크플로우 실행
    # ... (기존 워크플로우 로직)
```

## 설계 원칙

### 외부 검증 vs 내부 검증

| 항목 | 외부 검증 (채택) | 내부 검증 |
|------|-----------------|----------|
| 위치 | `workflow_service.py` | LangGraph 노드 내부 |
| LangGraph 영향 | 없음 | 노드 수정 필요 |
| 테스트 용이성 | 높음 (독립 테스트 가능) | 낮음 (워크플로우 테스트 필요) |
| 성능 | 빠름 (워크플로우 미실행) | 느림 (노드 진입 후 검증) |
| 유지보수성 | 높음 (단일 파일) | 낮음 (여러 노드에 분산) |

### 책임 분리

- **외부 검증 레이어**: 입력 형식 검증 (빈 입력, 길이)
- **LangGraph 내부**: 비즈니스 로직 관련 오류 처리 (RAG 실패, Intent 실패, LLM API 오류)

## 로깅

검증 실패 시 로그 출력:

```python
logger.warning(
    f"입력 검증 실패 - 세션: {request.session_id}, "
    f"유형: {validation_result.error_type}, "
    f"메시지 길이: {len(request.user_message) if request.user_message else 0}"
)
```

검증 통과 시 로그 출력:

```python
logger.debug(f"입력 검증 통과 - 세션: {request.session_id}")
```

## 테스트 시나리오

| 시나리오 | 입력 | 예상 결과 |
|---------|------|----------|
| 빈 입력 | `""` | error_type: "empty" |
| 공백만 | `"   "` | error_type: "empty" |
| 1자 입력 | `"a"` | error_type: "empty" |
| 2자 입력 | `"ab"` | 검증 통과 |
| 정상 입력 | `"카드 분실 신고"` | 검증 통과 |
| 2000자 입력 | `"a" * 2000` | 검증 통과 |
| 2001자 입력 | `"a" * 2001` | error_type: "too_long" |

## 향후 확장 가능성

- SQL Injection 패턴 검증
- XSS 패턴 검증
- 비속어 필터링 (현재 LangGraph 내부에서 처리)
- Rate Limiting 연동
