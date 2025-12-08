// WebSocket 클라이언트 서비스

import type { ChatResponse } from '../types/api';

type MessageHandler = (response: ChatResponse) => void;
type ErrorHandler = (error: string) => void;
type StatusHandler = (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;
type HandoverReportHandler = (report: any) => void;

interface WebSocketMessage {
  type: 'response' | 'error' | 'status' | 'processing' | 'pong' | 'handover_processing' | 'handover_report' | 'handover_error';
  message?: string;
  data?: any;
  session_id?: string;
  timestamp?: number;
}

/**
 * WebSocket 클라이언트 서비스
 * 실시간 양방향 통신을 위한 WebSocket 연결 관리
 */
export class WebSocketService {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000; // 2초
  private pingInterval: NodeJS.Timeout | null = null;
  private messageHandlers: MessageHandler[] = [];
  private errorHandlers: ErrorHandler[] = [];
  private statusHandlers: StatusHandler[] = [];
  private handoverReportHandlers: HandoverReportHandler[] = [];

  /**
   * WebSocket 연결
   */
  connect(sessionId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.sessionId = sessionId;
      
      // 기존 연결이 있으면 종료
      if (this.ws) {
        this.disconnect();
      }

      // WebSocket URL 생성
      const wsUrl = this.getWebSocketUrl(sessionId);
      console.log('WebSocket 연결 시도:', wsUrl);
      
      this.notifyStatus('connecting');

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('WebSocket 연결 성공');
          this.reconnectAttempts = 0;
          this.notifyStatus('connected');
          this.startPingInterval();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('메시지 파싱 오류:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket 오류:', error);
          this.notifyStatus('error');
          this.notifyError('WebSocket 연결 오류가 발생했습니다.');
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket 연결 종료:', event.code, event.reason);
          this.stopPingInterval();
          this.notifyStatus('disconnected');

          // 정상 종료가 아니면 재연결 시도
          if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };
      } catch (error) {
        console.error('WebSocket 생성 오류:', error);
        this.notifyStatus('error');
        reject(error);
      }
    });
  }

  /**
   * WebSocket URL 생성
   */
  private getWebSocketUrl(sessionId: string): string {
    // 환경 변수에서 WebSocket URL 가져오기
    const wsBaseUrl = import.meta.env.VITE_WS_URL;
    
    if (wsBaseUrl) {
      return `${wsBaseUrl}/${sessionId}`;
    }

    // 기본값: 항상 백엔드 포트(8000) 사용
    console.log('환경 변수 없음, 기본 URL 사용: ws://localhost:8000');
    return `ws://localhost:8000/api/v1/chat/ws/${sessionId}`;
  }

  /**
   * 메시지 전송
   */
  sendMessage(userMessage: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.notifyError('WebSocket이 연결되어 있지 않습니다.');
      return;
    }

    try {
      this.ws.send(JSON.stringify({
        type: 'message',
        user_message: userMessage,
      }));
    } catch (error) {
      console.error('메시지 전송 오류:', error);
      this.notifyError('메시지 전송에 실패했습니다.');
    }
  }

  /**
   * 연결 해제
   */
  disconnect(): void {
    this.stopPingInterval();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.sessionId = null;
    this.reconnectAttempts = 0;
  }

  /**
   * 메시지 핸들러 등록
   */
  onMessage(handler: MessageHandler): void {
    this.messageHandlers.push(handler);
  }

  /**
   * 에러 핸들러 등록
   */
  onError(handler: ErrorHandler): void {
    this.errorHandlers.push(handler);
  }

  /**
   * 상태 핸들러 등록
   */
  onStatus(handler: StatusHandler): void {
    this.statusHandlers.push(handler);
  }

  /**
   * 상담원 리포트 핸들러 등록
   */
  onHandoverReport(handler: HandoverReportHandler): void {
    this.handoverReportHandlers.push(handler);
  }

  /**
   * 상담원 이관 요청
   */
  requestHandover(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.notifyError('WebSocket이 연결되어 있지 않습니다.');
      return;
    }

    try {
      this.ws.send(JSON.stringify({
        type: 'request_handover',
      }));
      console.log('상담원 이관 요청 전송');
    } catch (error) {
      console.error('상담원 이관 요청 오류:', error);
      this.notifyError('상담원 이관 요청에 실패했습니다.');
    }
  }

  /**
   * 연결 상태 확인
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * 메시지 처리
   */
  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'response':
        if (message.data) {
          this.notifyMessage(message.data);
        }
        break;

      case 'error':
        if (message.message) {
          this.notifyError(message.message);
        }
        break;

      case 'status':
        console.log('서버 상태:', message.message);
        if (message.message === 'connected') {
          this.notifyStatus('connected');
        }
        break;

      case 'processing':
        console.log('처리 중:', message.message);
        break;

      case 'handover_processing':
        console.log('상담원 리포트 생성 중:', message.message);
        break;

      case 'handover_report':
        console.log('상담원 리포트 수신:', message.data);
        if (message.data) {
          this.notifyHandoverReport(message.data);
        }
        break;

      case 'handover_error':
        console.error('상담원 리포트 오류:', message.message);
        if (message.message) {
          this.notifyError(message.message);
        }
        break;

      case 'pong':
        // Ping 응답 수신
        break;

      default:
        console.warn('알 수 없는 메시지 타입:', message.type);
    }
  }

  /**
   * 메시지 핸들러 호출
   */
  private notifyMessage(response: ChatResponse): void {
    this.messageHandlers.forEach(handler => handler(response));
  }

  /**
   * 에러 핸들러 호출
   */
  private notifyError(error: string): void {
    this.errorHandlers.forEach(handler => handler(error));
  }

  /**
   * 상태 핸들러 호출
   */
  private notifyStatus(status: 'connecting' | 'connected' | 'disconnected' | 'error'): void {
    this.statusHandlers.forEach(handler => handler(status));
  }

  /**
   * 상담원 리포트 핸들러 호출
   */
  private notifyHandoverReport(report: any): void {
    this.handoverReportHandlers.forEach(handler => handler(report));
  }

  /**
   * 재연결 시도
   */
  private attemptReconnect(): void {
    this.reconnectAttempts++;
    console.log(`재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);

    setTimeout(() => {
      if (this.sessionId) {
        this.connect(this.sessionId).catch(error => {
          console.error('재연결 실패:', error);
        });
      }
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  /**
   * Ping 인터벌 시작 (연결 유지)
   */
  private startPingInterval(): void {
    this.stopPingInterval();

    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({
            type: 'ping',
            timestamp: Date.now(),
          }));
        } catch (error) {
          console.error('Ping 전송 오류:', error);
        }
      }
    }, 30000); // 30초마다 Ping
  }

  /**
   * Ping 인터벌 중지
   */
  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}

// 싱글톤 인스턴스
export const websocketService = new WebSocketService();

