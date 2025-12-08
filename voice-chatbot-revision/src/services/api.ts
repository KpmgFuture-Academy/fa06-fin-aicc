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

export interface HandoverResponse {
  session_id: string;
  status: string;
  trigger_reason: string;
  priority: string;
  ai_analysis: {
    intent: string;
    sentiment: string;
    key_issues: string[];
    recommended_department: string;
    summary: string;
  };
  message: string;
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
};

/**
 * 세션 ID 생성/조회
 */
export const getOrCreateSessionId = (): string => {
  const key = 'voice_session_id';
  let sessionId = localStorage.getItem(key);

  if (!sessionId) {
    sessionId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
    localStorage.setItem(key, sessionId);
  }

  return sessionId;
};

export const resetSessionId = (): void => {
  localStorage.removeItem('voice_session_id');
};
