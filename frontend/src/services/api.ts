// API 클라이언트 서비스

import axios from 'axios';
import type { ChatRequest, ChatResponse, HandoverRequest, HandoverResponse } from '../types/api';
import { websocketService } from './websocket';

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
   * 채팅 메시지 전송 (HTTP)
   * WebSocket 사용 불가 시 fallback으로 사용
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/api/v1/chat/message', request);
    return response.data;
  },

  /**
   * 채팅 메시지 전송 (WebSocket 우선, HTTP fallback)
   * @param request - 채팅 요청
   * @param onMessage - WebSocket 응답 콜백
   * @param useWebSocket - WebSocket 사용 여부 (기본값: true)
   */
  async sendMessageWithWebSocket(
    request: ChatRequest,
    onMessage: (response: ChatResponse) => void,
    useWebSocket: boolean = true
  ): Promise<ChatResponse | null> {
    // WebSocket이 활성화되고 연결 가능한 경우
    if (useWebSocket && websocketService.isConnected()) {
      // WebSocket으로 메시지 전송
      websocketService.sendMessage(request.user_message);
      return null; // WebSocket은 비동기 콜백으로 응답
    }

    // HTTP fallback
    console.log('WebSocket 사용 불가, HTTP로 요청');
    return await this.sendMessage(request);
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

