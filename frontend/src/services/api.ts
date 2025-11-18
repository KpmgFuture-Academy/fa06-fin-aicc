// API 클라이언트 서비스

import axios from 'axios';
import type { ChatRequest, ChatResponse, HandoverRequest, HandoverResponse } from '../types/api';

// 백엔드 서버 직접 연결 (프록시 대신)
// 환경 변수가 없으면 기본값으로 localhost:8000 사용
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// LM Studio 로컬 모델은 응답이 느릴 수 있으므로 타임아웃을 길게 설정
const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || '300000', 10); // 기본 5분 (300초)

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: API_TIMEOUT, // 로컬 모델을 위해 5분으로 설정
});

export const chatApi = {
  /**
   * 채팅 메시지 전송
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/api/v1/chat/message', request);
    return response.data;
  },

  /**
   * 상담원 이관 요청
   */
  async requestHandover(request: HandoverRequest): Promise<HandoverResponse> {
    const response = await apiClient.post<HandoverResponse>('/api/v1/handover/analyze', request);
    return response.data;
  },

  /**
   * 헬스체크
   */
  async healthCheck(): Promise<{ status: string; database: string }> {
    const response = await apiClient.get('/health');
    return response.data;
  },
};

export default chatApi;

