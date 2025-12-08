// WebSocket 클라이언트 서비스 (음성 전용)

type MessageHandler = (type: string, data: any) => void;
type ErrorHandler = (error: string) => void;
type StatusHandler = (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;

interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: number;
}

/**
 * 음성 WebSocket 서비스
 * 실시간 양방향 음성 통신을 위한 WebSocket 연결 관리
 */
export class VoiceWebSocketService {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000; // 2초
  private pingInterval: number | null = null;
  private messageHandlers: MessageHandler[] = [];
  private errorHandlers: ErrorHandler[] = [];
  private statusHandlers: StatusHandler[] = [];

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
      console.log('음성 WebSocket 연결 시도:', wsUrl);
      
      this.notifyStatus('connecting');

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          console.log('음성 WebSocket 연결 성공');
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
          console.error('WebSocket 오류 발생:', error);
          console.error('연결 URL:', wsUrl);
          console.error('세션 ID:', sessionId);
          this.notifyStatus('error');
          this.notifyError(`WebSocket 연결 오류: ${wsUrl}`);
          reject(error);
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket 연결 종료:', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
            url: wsUrl
          });
          
          // 에러 코드별 상세 로그
          if (event.code === 1006) {
            console.error('❌ 연결이 비정상적으로 종료되었습니다 (1006)');
            console.error('   가능한 원인: 서버가 실행 중이지 않거나, 네트워크 문제');
          } else if (event.code === 1000) {
            console.log('✅ 정상 종료 (1000)');
          } else {
            console.warn(`⚠️ 종료 코드: ${event.code}, 이유: ${event.reason || '없음'}`);
          }
          
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
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    
    if (wsBaseUrl) {
      const url = `${wsBaseUrl}/voice/ws/${sessionId}`;
      console.log('환경 변수에서 WebSocket URL 사용:', url);
      return url;
    }

    // API Base URL에서 WebSocket URL 생성
    // http://localhost:8000 -> ws://localhost:8000
    const wsUrl = apiBaseUrl.replace(/^http/, 'ws');
    const fullUrl = `${wsUrl}/api/v1/voice/ws/${sessionId}`;
    console.log('기본 WebSocket URL 생성:', fullUrl);
    return fullUrl;
  }

  /**
   * 음성 전송 시작
   */
  sendAudioStart(language: string = 'ko', ttsVoice: string = 'alloy'): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.notifyError('WebSocket이 연결되어 있지 않습니다.');
      return;
    }

    try {
      this.ws.send(JSON.stringify({
        type: 'audio_start',
        data: {
          language,
          tts_voice: ttsVoice,
          diarize: false,
        },
      }));
      console.log('음성 전송 시작:', { language, tts_voice: ttsVoice });
    } catch (error) {
      console.error('음성 시작 메시지 전송 오류:', error);
      this.notifyError('음성 전송 시작에 실패했습니다.');
    }
  }

  /**
   * 음성 청크 전송 (Base64)
   */
  sendAudioChunk(audioBase64: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.notifyError('WebSocket이 연결되어 있지 않습니다.');
      return;
    }

    try {
      this.ws.send(JSON.stringify({
        type: 'audio_chunk',
        data: {
          audio_base64: audioBase64,
        },
      }));
    } catch (error) {
      console.error('음성 청크 전송 오류:', error);
      this.notifyError('음성 데이터 전송에 실패했습니다.');
    }
  }

  /**
   * 음성 전송 종료
   */
  sendAudioEnd(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.notifyError('WebSocket이 연결되어 있지 않습니다.');
      return;
    }

    try {
      this.ws.send(JSON.stringify({
        type: 'audio_end',
      }));
      console.log('음성 전송 종료');
    } catch (error) {
      console.error('음성 종료 메시지 전송 오류:', error);
      this.notifyError('음성 전송 종료에 실패했습니다.');
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
      case 'connected':
        console.log('서버 연결 확인:', message.data);
        break;

      case 'stt_result':
        console.log('STT 결과 수신:', message.data);
        this.notifyMessage('stt_result', message.data);
        break;

      case 'ai_response':
        console.log('AI 응답 수신:', message.data);
        this.notifyMessage('ai_response', message.data);
        break;

      case 'tts_audio':
        console.log('TTS 오디오 수신');
        this.notifyMessage('tts_audio', message.data);
        break;

      case 'error':
        console.error('서버 에러:', message.data);
        if (message.data?.error) {
          this.notifyError(message.data.error);
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
  private notifyMessage(type: string, data: any): void {
    this.messageHandlers.forEach(handler => handler(type, data));
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
export const voiceWebSocketService = new VoiceWebSocketService();

