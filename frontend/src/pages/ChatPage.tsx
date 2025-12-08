import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ChatWindow from '../components/ChatWindow';
import { chatApi } from '../services/api';
import { websocketService } from '../services/websocket';
import { getOrCreateSessionId, resetSessionId } from '../utils/session';
import type { Message, ChatResponse } from '../types/api';
import './ChatPage.css';

function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => getOrCreateSessionId());
  const [useWebSocket, setUseWebSocket] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const isWebSocketSetup = useRef(false);
  const navigate = useNavigate();

  // WebSocket 초기화 및 이벤트 핸들러 설정
  useEffect(() => {
    if (isWebSocketSetup.current) return;
    isWebSocketSetup.current = true;

    // WebSocket 연결 시도
    const initWebSocket = async () => {
      try {
        console.log('WebSocket 초기화 시작...');
        
        // 메시지 핸들러 등록
        websocketService.onMessage((response: ChatResponse) => {
          console.log('WebSocket 메시지 수신:', response);
          setMessages((prev) => [...prev, {
            id: `msg_${Date.now()}_${Math.random()}`,
            role: 'assistant',
            content: response.ai_message,
            timestamp: new Date(),
            intent: response.intent,
            suggested_action: response.suggested_action,
            source_documents: response.source_documents,
          }]);
          setIsLoading(false);
        });

        // 에러 핸들러 등록
        websocketService.onError((error: string) => {
          console.error('WebSocket 에러:', error);
          setIsLoading(false);
        });

        // 상태 핸들러 등록
        websocketService.onStatus((status) => {
          console.log('WebSocket 상태 변경:', status);
          setConnectionStatus(status);
          
          // 연결 성공 시
          if (status === 'connected') {
            setUseWebSocket(true);
            console.log('✅ WebSocket 모드 활성화');
          }
          
          // 연결 실패 시 HTTP fallback
          if (status === 'error' || status === 'disconnected') {
            setUseWebSocket(false);
            console.log('WebSocket 사용 불가, HTTP 모드로 전환');
          }
        });

        // 약간의 지연 후 연결 (백엔드 준비 대기)
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // WebSocket 연결
        console.log('WebSocket 연결 시도:', sessionId);
        await websocketService.connect(sessionId);
        console.log('WebSocket 연결 요청 완료');
      } catch (error) {
        console.error('WebSocket 초기화 실패, HTTP 모드 사용:', error);
        setUseWebSocket(false);
        setConnectionStatus('error');
      }
    };

    initWebSocket();

    // 컴포넌트 언마운트 시 WebSocket 연결 해제
    return () => {
      websocketService.disconnect();
    };
  }, [sessionId]);

  const addMessage = useCallback((role: 'user' | 'assistant', content: string, response?: ChatResponse) => {
    const newMessage: Message = {
      id: `msg_${Date.now()}_${Math.random()}`,
      role,
      content,
      timestamp: new Date(),
      intent: response?.intent,
      suggested_action: response?.suggested_action,
      source_documents: response?.source_documents,
    };
    setMessages((prev) => [...prev, newMessage]);
  }, []);

  const handleSendMessage = useCallback(async (userMessage: string) => {
    // 사용자 메시지 추가
    addMessage('user', userMessage);

    setIsLoading(true);
    try {
      // WebSocket 우선, HTTP fallback
      if (useWebSocket && websocketService.isConnected()) {
        console.log('WebSocket으로 메시지 전송:', {
          session_id: sessionId,
          user_message: userMessage,
          connection_status: connectionStatus
        });
        
        // WebSocket으로 메시지 전송
        websocketService.sendMessage(userMessage);
        
        // WebSocket은 비동기 콜백으로 응답 받음 (onMessage 핸들러)
      } else {
        // HTTP fallback
        console.log('HTTP API 호출 시작:', {
          session_id: sessionId,
          user_message: userMessage,
          api_url: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
          reason: useWebSocket ? 'WebSocket 연결 끊김' : 'WebSocket 비활성화'
        });
        
        const response = await chatApi.sendMessage({
          session_id: sessionId,
          user_message: userMessage,
        });
        
        console.log('HTTP API 응답:', response);
        addMessage('assistant', response.ai_message, response);
        setIsLoading(false);
      }
    } catch (error) {
      console.error('메시지 전송 실패:', error);
      
      // 에러 메시지를 사용자에게 표시
      addMessage('assistant', '죄송합니다. 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
      setIsLoading(false);
    }
  }, [sessionId, addMessage, useWebSocket, connectionStatus]);

  const handleNewSession = useCallback(() => {
    if (window.confirm('새로운 상담을 시작하시겠습니까? 현재 대화 내용이 초기화됩니다.')) {
      resetSessionId();
      window.location.reload();
    }
  }, []);

  return (
    <div className="chat-page">
      <header className="chat-header">
        <h1>🏦 Bank AICC 상담 챗봇</h1>
        <div className="header-buttons">
          <button
            className="btn-new-session"
            onClick={handleNewSession}
          >
            🔄 새 세션
          </button>
          <button
            className="btn-consultant"
            onClick={() => navigate('/consultant')}
          >
            🎧 상담원 대시보드
          </button>
        </div>
      </header>
      
      <div className="status-indicator">
        {connectionStatus === 'connected' && useWebSocket && (
          <span className="status-badge connected">🟢 WebSocket 연결</span>
        )}
        {!useWebSocket && (
          <span className="status-badge http">🔵 HTTP 모드</span>
        )}
        {connectionStatus === 'error' && (
          <span className="status-badge error">🔴 연결 오류</span>
        )}
      </div>

      <ChatWindow
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        sessionId={sessionId}
      />
    </div>
  );
}

export default ChatPage;

