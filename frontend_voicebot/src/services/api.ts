import axios from 'axios';

const API_BASE_URL = '/api/v1';

export interface VoiceChatResponse {
  ai_message: string;
  audio_base64: string | null;
  audio_format: string;
  intent: string;
  suggested_action: string;
  transcribed_text: string;
  stt_duration_ms: number;
  tts_duration_ms: number | null;
  total_duration_ms: number;
}

export interface TextChatResponse {
  ai_message: string;
  intent: string;
  suggested_action: string;
  source_documents: Array<{
    title: string;
    content: string;
    score: number;
  }>;
  info_collection_complete?: boolean;
  handover_status?: 'pending' | 'accepted' | 'declined' | 'timeout' | null;
}

export interface HandoverResponse {
  status: string;
  analysis_result: {
    customer_sentiment: string;
    summary: string;
    extracted_keywords: string[];
    kms_recommendations: Array<{
      title: string;
      url: string;
      relevance_score: number;
    }>;
  };
}

export interface HandoverStatusResponse {
  session_id: string;
  handover_status: 'pending' | 'accepted' | 'declined' | 'timeout' | null;
  handover_requested_at: string | null;
  handover_accepted_at: string | null;
  assigned_agent_id: string | null;
}

export const voiceApi = {
  /**
   * 음성 메시지 전송 (STT → AI → TTS)
   */
  sendVoiceMessage: async (
    sessionId: string,
    audioBlob: Blob
  ): Promise<VoiceChatResponse> => {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('language', 'ko');

    const response = await axios.post<VoiceChatResponse>(
      `${API_BASE_URL}/voice/message`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 60초 타임아웃
      }
    );

    return response.data;
  },

  /**
   * 상담원 이관 요청
   */
  requestHandover: async (
    sessionId: string,
    triggerReason: string = 'USER_REQUEST'
  ): Promise<HandoverResponse> => {
    const response = await axios.post<HandoverResponse>(
      `${API_BASE_URL}/handover/request`,
      {
        session_id: sessionId,
        trigger_reason: triggerReason,
      }
    );
    return response.data;
  },

  /**
   * 고객 메시지 전송 (이관 모드에서 상담원에게)
   * AI를 거치지 않고 직접 DB에 저장
   */
  sendCustomerMessage: async (
    sessionId: string,
    message: string
  ): Promise<{ success: boolean; message_id: number; created_at: string }> => {
    const response = await axios.post(
      `${API_BASE_URL}/sessions/${sessionId}/customer-message`,
      { message }
    );
    return response.data;
  },

  /**
   * 텍스트 메시지 전송 (텍스트 → AI)
   */
  sendTextMessage: async (
    sessionId: string,
    userMessage: string
  ): Promise<TextChatResponse> => {
    const response = await axios.post<TextChatResponse>(
      `${API_BASE_URL}/chat/message`,
      {
        session_id: sessionId,
        user_message: userMessage,
      },
      {
        timeout: 60000, // 60초 타임아웃
      }
    );
    return response.data;
  },

  /**
   * TTS 요청 (텍스트 → 음성)
   */
  requestTTS: async (
    text: string
  ): Promise<{ audio_base64: string; format: string }> => {
    const response = await axios.post(
      `${API_BASE_URL}/voice/tts`,
      { text },
      {
        timeout: 30000,
      }
    );
    return response.data;
  },

  /**
   * 핸드오버 요청 (상담사 연결 대기 시작)
   */
  requestHandoverWithStatus: async (
    sessionId: string
  ): Promise<{ success: boolean; message: string; handover_status: string }> => {
    const response = await axios.post(
      `${API_BASE_URL}/sessions/${sessionId}/request-handover`
    );
    return response.data;
  },

  /**
   * 핸드오버 상태 조회 (폴링용)
   */
  getHandoverStatus: async (
    sessionId: string
  ): Promise<HandoverStatusResponse> => {
    const response = await axios.get<HandoverStatusResponse>(
      `${API_BASE_URL}/sessions/${sessionId}/handover-status`
    );
    return response.data;
  },

  /**
   * 고객이 상담사 연결 확인 (accepted 상태에서)
   * 실제 핸드오버 모드로 전환
   */
  confirmHandover: async (
    sessionId: string
  ): Promise<HandoverResponse> => {
    const response = await axios.post<HandoverResponse>(
      `${API_BASE_URL}/handover/request`,
      {
        session_id: sessionId,
        trigger_reason: 'CUSTOMER_CONFIRMED',
      }
    );
    return response.data;
  },
};

/**
 * 세션 ID 생성/조회
 * 형식: YYYYMMDD_HHmm_XXX (날짜_시간_순번)
 * 예: 20251210_1430_001
 */
export const getOrCreateSessionId = (): string => {
  const key = 'voice_session_id';
  let sessionId = localStorage.getItem(key);

  if (!sessionId) {
    sessionId = generateSessionId();
    localStorage.setItem(key, sessionId);
  }

  return sessionId;
};

/**
 * 세션 ID 포맷 생성
 */
const generateSessionId = (): string => {
  const now = new Date();

  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hour = String(now.getHours()).padStart(2, '0');
  const minute = String(now.getMinutes()).padStart(2, '0');

  // 오늘 날짜 기준 순번 (localStorage에 저장)
  const dateKey = `${year}${month}${day}`;
  const counterKey = `session_counter_${dateKey}`;
  let counter = parseInt(localStorage.getItem(counterKey) || '0', 10) + 1;
  localStorage.setItem(counterKey, String(counter));

  const seq = String(counter).padStart(3, '0');

  return `${year}${month}${day}_${hour}${minute}_${seq}`;
};

/**
 * 세션 ID를 보기 좋게 포맷팅
 * 예: 20251210_1430_001 → 2025-12-10 14:30 #001
 */
export const formatSessionIdForDisplay = (sessionId: string): string => {
  // 새 형식 (YYYYMMDD_HHmm_XXX)
  const newFormatMatch = sessionId.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})_(\d{3})$/);
  if (newFormatMatch) {
    const [, , month, day, hour, minute, seq] = newFormatMatch;
    return `${month}-${day} ${hour}:${minute} #${seq}`;
  }

  // 기존 형식 (sess_timestamp_random) - 호환성 유지
  if (sessionId.startsWith('sess_')) {
    return sessionId.slice(0, 15) + '...';
  }

  return sessionId;
};

export const resetSessionId = (): void => {
  localStorage.removeItem('voice_session_id');
};
