# 정보 수집 상태 관리 DB 전환 가이드라인

## 개요

현재는 **옵션 B (conversation_history 분석)** 방식으로 정보 수집 상태를 관리하고 있습니다.
이 문서는 나중에 **옵션 A (DB 저장)** 방식으로 전환할 때 필요한 수정 사항을 안내합니다.

---

## 현재 상태 (옵션 B)

### 구현 방식
- `workflow_service.py`의 `_restore_info_collection_state()` 함수가 conversation_history를 분석하여 상태 복원
- 메시지 텍스트 패턴 기반으로 정보 수집 단계 여부 및 질문 횟수 추정

### 장점
- DB 스키마 변경 불필요
- 빠른 적용 가능

### 단점
- 메시지 텍스트 변경에 취약
- 질문 카운팅 정확도 제한
- 매 턴마다 대화 이력 파싱 필요

---

## 전환 목표 (옵션 A)

### 구현 방식
- `ChatSession` 모델에 정보 수집 상태 필드 추가
- `chat_db_storage_node`에서 상태 저장
- `chat_request_to_state`에서 DB에서 상태 복원

### 장점
- 정확한 상태 관리
- 메시지 텍스트 변경에 영향 없음
- 성능 향상 (대화 이력 파싱 불필요)
- 확장성 (추가 상태 필드 저장 용이)

---

## 단계별 마이그레이션 가이드

### 1단계: DB 모델 수정

**파일**: `app/models/chat_message.py`

**수정 내용**:
```python
class ChatSession(Base):
    """채팅 세션 테이블"""
    __tablename__ = "chat_sessions"
    
    # ... 기존 필드들 ...
    is_active = Column(Integer, default=1, nullable=False)
    
    # ========== 정보 수집 단계 관련 필드 추가 ==========
    is_collecting_info = Column(Integer, default=0, nullable=False)  # 0: False, 1: True
    info_collection_count = Column(Integer, default=0, nullable=False)  # 정보 수집 질문 횟수 (0~6)
    
    # 관계
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
```

**주의사항**:
- `Integer` 타입 사용 (MySQL Boolean 호환성)
- `nullable=False`, `default=0` 설정
- 기존 데이터는 기본값(0)으로 자동 설정됨

---

### 2단계: DB 마이그레이션 스크립트 작성

**파일**: `scripts/migrate_add_info_collection_fields.sql`

**내용**:
```sql
-- 정보 수집 상태 필드 추가 마이그레이션
-- 사용법: mysql -u root -p aicc_db < scripts/migrate_add_info_collection_fields.sql

USE aicc_db;

-- 필드 추가 (MySQL 5.7 이상)
ALTER TABLE chat_sessions 
ADD COLUMN is_collecting_info INT DEFAULT 0 NOT NULL COMMENT '정보 수집 단계 여부 (0: False, 1: True)',
ADD COLUMN info_collection_count INT DEFAULT 0 NOT NULL COMMENT '정보 수집 질문 횟수 (0~6)';

-- 기존 데이터 마이그레이션 (선택사항)
-- conversation_history를 분석하여 기존 세션의 상태 복원
-- 이 부분은 필요에 따라 Python 스크립트로 작성 가능
```

**실행 방법**:
```bash
# MySQL에 접속하여 실행
mysql -u root -p aicc_db < scripts/migrate_add_info_collection_fields.sql

# 또는 MySQL 클라이언트에서 직접 실행
mysql -u root -p
USE aicc_db;
SOURCE scripts/migrate_add_info_collection_fields.sql;
```

**주의사항**:
- 프로덕션 환경에서는 백업 후 실행
- MySQL 버전에 따라 `IF NOT EXISTS` 지원 여부 확인
- 기존 데이터가 있는 경우 마이그레이션 스크립트 작성 고려

---

### 3단계: 상태 저장 로직 추가

**파일**: `ai_engine/graph/nodes/chat_db_storage.py`

**수정 위치**: 79-83줄 (세션 업데이트 시간 갱신 부분 이후)

**수정 전**:
```python
# 세션 업데이트 시간 갱신
chat_session.updated_at = datetime.utcnow()

# 커밋
db.commit()
```

**수정 후**:
```python
# 세션 업데이트 시간 갱신
chat_session.updated_at = datetime.utcnow()

# 정보 수집 상태 저장
is_collecting_info = state.get("is_collecting_info", False)
info_collection_count = state.get("info_collection_count", 0)
chat_session.is_collecting_info = 1 if is_collecting_info else 0
chat_session.info_collection_count = info_collection_count

# 커밋
db.commit()
```

**주의사항**:
- Boolean → Integer 변환 (0 또는 1)
- 새 세션 생성 시(35-42줄)에도 기본값이 자동 설정됨 (모델의 default 값)

---

### 4단계: 상태 복원 로직 수정

**파일**: `app/services/workflow_service.py`

**수정 위치**: `chat_request_to_state` 함수 (70-95줄)

**수정 전** (옵션 B):
```python
def chat_request_to_state(request: ChatRequest) -> GraphState:
    conversation_history = session_manager.get_conversation_history(request.session_id)
    conversation_turn = len([msg for msg in conversation_history if msg.get("role") == "user"])
    
    # conversation_history를 분석하여 정보 수집 상태 복원
    is_collecting_info, info_collection_count = _restore_info_collection_state(conversation_history)
    
    state: GraphState = {
        # ...
        "is_collecting_info": is_collecting_info,
        "info_collection_count": info_collection_count,
    }
    return state
```

**수정 후** (옵션 A):
```python
def chat_request_to_state(request: ChatRequest) -> GraphState:
    conversation_history = session_manager.get_conversation_history(request.session_id)
    conversation_turn = len([msg for msg in conversation_history if msg.get("role") == "user"])
    
    # DB에서 정보 수집 상태 복원
    from app.core.database import SessionLocal
    from app.models.chat_message import ChatSession
    
    db = SessionLocal()
    try:
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == request.session_id,
            ChatSession.is_active == 1
        ).first()
        
        if chat_session:
            # DB에서 상태 복원
            is_collecting_info = bool(chat_session.is_collecting_info)
            info_collection_count = chat_session.info_collection_count
        else:
            # 세션이 없으면 기본값
            is_collecting_info = False
            info_collection_count = 0
    except Exception as e:
        # 에러 발생 시 기본값 사용 및 로깅
        logger.warning(f"정보 수집 상태 복원 실패 - 세션: {request.session_id}, 오류: {str(e)}")
        is_collecting_info = False
        info_collection_count = 0
    finally:
        db.close()
    
    state: GraphState = {
        "session_id": request.session_id,
        "user_message": request.user_message,
        "conversation_history": conversation_history,
        "conversation_turn": conversation_turn + 1,
        "is_new_turn": True,
        "processing_start_time": datetime.now().isoformat(),
        "is_collecting_info": is_collecting_info,  # DB에서 복원한 값
        "info_collection_count": info_collection_count,  # DB에서 복원한 값
    }
    return state
```

**주의사항**:
- `SessionLocal`, `ChatSession` import 추가
- 에러 처리 및 로깅 추가
- DB 연결은 `finally` 블록에서 반드시 닫기

---

### 5단계: (선택) 기존 함수 제거 또는 주석 처리

**파일**: `app/services/workflow_service.py`

**옵션 1: 함수 제거**
```python
# _restore_info_collection_state 함수 삭제
# 더 이상 사용하지 않으므로 제거
```

**옵션 2: 함수 주석 처리 (백업용)**
```python
# def _restore_info_collection_state(...):
#     """옵션 B 방식 - 더 이상 사용하지 않음 (백업용)"""
#     ...
```

**권장**: 옵션 2 (백업용으로 주석 처리)
- 나중에 문제 발생 시 참고 가능
- 완전히 제거하기 전에 충분한 테스트 기간 확보

---

## 마이그레이션 체크리스트

### 사전 준비
- [ ] 프로덕션 환경 DB 백업
- [ ] 개발 환경에서 테스트 완료
- [ ] 마이그레이션 스크립트 검증

### 코드 수정
- [ ] `app/models/chat_message.py` - ChatSession 모델 수정
- [ ] `ai_engine/graph/nodes/chat_db_storage.py` - 상태 저장 로직 추가
- [ ] `app/services/workflow_service.py` - 상태 복원 로직 수정
- [ ] (선택) `_restore_info_collection_state` 함수 주석 처리

### DB 마이그레이션
- [ ] 마이그레이션 스크립트 작성
- [ ] 개발 환경에서 마이그레이션 테스트
- [ ] 프로덕션 환경 마이그레이션 실행

### 테스트
- [ ] 정보 수집 시작 → 5회 질문 → 6번째 메시지 플로우 테스트
- [ ] 여러 턴에 걸친 상태 유지 확인
- [ ] 에러 발생 시 복구 확인
- [ ] 기존 세션과 새 세션 모두 테스트

### 배포
- [ ] 코드 배포
- [ ] DB 마이그레이션 실행
- [ ] 모니터링 및 로그 확인

---

## 롤백 계획

문제 발생 시 롤백 방법:

### 1. 코드 롤백
- 이전 버전의 `workflow_service.py`로 복원
- `_restore_info_collection_state` 함수 활성화

### 2. DB 롤백 (필요 시)
```sql
-- 필드 제거 (주의: 데이터 손실)
ALTER TABLE chat_sessions 
DROP COLUMN is_collecting_info,
DROP COLUMN info_collection_count;
```

---

## 추가 고려사항

### 정보 수집 완료 후 상태 리셋

현재는 정보 수집 완료 후에도 상태가 유지됩니다. 필요하다면 리셋 로직 추가:

**위치**: `ai_engine/graph/workflow.py`의 `_route_after_answer` 함수

```python
def _route_after_answer(state: GraphState) -> str:
    info_collection_count = state.get("info_collection_count", 0)
    
    if info_collection_count >= 6:
        # 정보 수집 완료 후 상태 리셋 (선택사항)
        state["is_collecting_info"] = False
        state["info_collection_count"] = 0
        return "summary_agent"
    return "chat_db_storage"
```

**주의**: 상태를 리셋하면 `chat_db_storage_node`에서 DB에도 저장되므로, 다음 턴부터는 일반 대화로 처리됩니다.

### 성능 최적화

DB 조회 최적화를 위해 인덱스 추가 고려:

```sql
-- 인덱스 추가 (선택사항)
CREATE INDEX idx_is_collecting_info ON chat_sessions(is_collecting_info);
```

---

## 참고 사항

### 현재 구현 (옵션 B)의 한계
- 메시지 텍스트 변경 시 로직 수정 필요
- 질문 카운팅 정확도 제한
- 매 턴마다 대화 이력 파싱

### 옵션 A 전환 후 개선 사항
- 정확한 상태 관리
- 메시지 텍스트 변경에 영향 없음
- 성능 향상
- 확장성 향상

---

## 문의 및 지원

마이그레이션 중 문제 발생 시:
1. 로그 확인 (`app/services/workflow_service.py`의 logger)
2. DB 상태 확인 (`chat_sessions` 테이블)
3. 롤백 계획 실행

---

**작성일**: 2024
**버전**: 1.0
**상태**: 옵션 B → 옵션 A 전환 가이드

