const API_BASE_URL = 'http://localhost:8000/api/v1';

export interface ChatRequest {
  session_id: string;
  user_message: string;
}

export interface ChatResponse {
  ai_message: string;
  intent: string;
  suggested_action: 'CONTINUE' | 'HANDOVER';
  source_documents: string[];
}

export interface HandoverRequest {
  session_id: string;
  trigger_reason: string;
}

export interface HandoverAnalysisResult {
  customer_sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  summary: string;
  extracted_keywords: string[];
  kms_recommendations: string[];
}

export interface HandoverResponse {
  status: string;
  analysis_result: HandoverAnalysisResult;
}

export interface Message {
  id: number;
  speaker: 'customer' | 'bot' | 'agent' | 'system';
  message: string;
  timestamp: string;
  isAiGenerated?: boolean;  // AI 챗봇이 생성한 메시지인지 여부 (상담사가 직접 보낸 것과 구분)
}

// 채팅 메시지 전송
export const sendChatMessage = async (request: ChatRequest): Promise<ChatResponse> => {
  const response = await fetch(`${API_BASE_URL}/chat/message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status}`);
  }

  return response.json();
};

// 상담원 이관 분석
export const analyzeHandover = async (request: HandoverRequest): Promise<HandoverResponse> => {
  const response = await fetch(`${API_BASE_URL}/handover/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Handover API error: ${response.status}`);
  }

  return response.json();
};

// 현재 시간 포맷
export const getCurrentTimestamp = (): string => {
  const now = new Date();
  return now.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
};

// 세션 ID 생성
export const generateSessionId = (): string => {
  const date = new Date();
  const dateStr = date.toISOString().slice(0, 10).replace(/-/g, '');
  const random = Math.random().toString(36).substring(2, 8);
  return `session-${dateStr}-${random}`;
};

// ========== 상담원 대시보드용 API ==========

// 이관 대기 세션 정보
export interface HandoverSession {
  session_id: string;
  created_at: string;
  updated_at: string;
  collected_info: Record<string, string>;
}

// DB 메시지 정보
export interface DBMessage {
  id: number;
  role: string;  // 'user' | 'assistant'
  message: string;
  created_at: string;
}

// 이관 대기 세션 목록 조회
export const getHandoverSessions = async (): Promise<HandoverSession[]> => {
  const response = await fetch(`${API_BASE_URL}/sessions/handover`);

  if (!response.ok) {
    throw new Error(`Sessions API error: ${response.status}`);
  }

  return response.json();
};

// 세션 메시지 조회 (폴링용)
export const getSessionMessages = async (
  sessionId: string,
  afterId?: number,
  afterHandover: boolean = false
): Promise<DBMessage[]> => {
  const params = new URLSearchParams();
  if (afterId !== undefined) {
    params.append('after_id', afterId.toString());
  }
  if (afterHandover) {
    params.append('after_handover', 'true');
  }
  const queryString = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages${queryString}`);

  if (!response.ok) {
    throw new Error(`Messages API error: ${response.status}`);
  }

  return response.json();
};

// 상담원 메시지 전송
export const sendAgentMessage = async (
  sessionId: string,
  message: string
): Promise<{ success: boolean; message_id: number; created_at: string }> => {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`Send message API error: ${response.status}`);
  }

  return response.json();
};

// 세션 종료 (상담 완료)
export const closeSession = async (
  sessionId: string
): Promise<{ success: boolean; message: string }> => {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/close`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Close session API error: ${response.status}`);
  }

  return response.json();
};

// 종료된 세션 목록 조회 (상담 기록)
export const getClosedSessions = async (): Promise<HandoverSession[]> => {
  const response = await fetch(`${API_BASE_URL}/sessions/closed`);

  if (!response.ok) {
    throw new Error(`Closed sessions API error: ${response.status}`);
  }

  return response.json();
};

// 세션 전체 메시지 조회 (상담 기록용)
export const getAllSessionMessages = async (
  sessionId: string
): Promise<DBMessage[]> => {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/all-messages`);

  if (!response.ok) {
    throw new Error(`All messages API error: ${response.status}`);
  }

  return response.json();
};
