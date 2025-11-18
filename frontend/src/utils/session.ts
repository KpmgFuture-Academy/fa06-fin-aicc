// 세션 관리 유틸리티

/**
 * 세션 ID 생성
 */
export function generateSessionId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * 로컬 스토리지에서 세션 ID 가져오기 또는 생성
 */
export function getOrCreateSessionId(): string {
  const stored = localStorage.getItem('aicc_session_id');
  if (stored) {
    return stored;
  }
  const newSessionId = generateSessionId();
  localStorage.setItem('aicc_session_id', newSessionId);
  return newSessionId;
}

/**
 * 세션 ID 초기화
 */
export function resetSessionId(): string {
  const newSessionId = generateSessionId();
  localStorage.setItem('aicc_session_id', newSessionId);
  return newSessionId;
}

