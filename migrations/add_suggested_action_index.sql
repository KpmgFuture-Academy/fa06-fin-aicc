-- suggested_action 컬럼에 인덱스 추가 (HANDOVER 메시지 조회 최적화)
-- chat_messages 테이블에서 suggested_action='HANDOVER'인 메시지를 빠르게 찾기 위함

CREATE INDEX idx_suggested_action ON chat_messages(suggested_action);

-- 복합 인덱스: session_id + suggested_action (더 빠른 조회)
CREATE INDEX idx_session_suggested_action ON chat_messages(session_id, suggested_action);
