-- 핸드오버 상태 관리 컬럼 추가
-- chat_sessions 테이블에 handover_status, handover_requested_at, handover_accepted_at, assigned_agent_id 추가

-- MySQL 버전
ALTER TABLE chat_sessions
ADD COLUMN handover_status VARCHAR(20) NULL COMMENT 'pending, accepted, declined, timeout',
ADD COLUMN handover_requested_at DATETIME NULL COMMENT '핸드오버 요청 시각',
ADD COLUMN handover_accepted_at DATETIME NULL COMMENT '상담사 수락 시각',
ADD COLUMN assigned_agent_id VARCHAR(100) NULL COMMENT '배정된 상담사 ID';

-- 인덱스 추가 (핸드오버 상태별 조회 최적화)
CREATE INDEX idx_handover_status ON chat_sessions(handover_status);
