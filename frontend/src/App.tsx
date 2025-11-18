import React, { useState, useCallback } from 'react';
import ChatWindow from './components/ChatWindow';
import HandoverModal from './components/HandoverModal';
import { chatApi } from './services/api';
import { getOrCreateSessionId, resetSessionId } from './utils/session';
import type { Message, ChatResponse, HandoverResponse } from './types/api';
import './App.css';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => getOrCreateSessionId());
  const [handoverData, setHandoverData] = useState<HandoverResponse | null>(null);

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
      // 디버깅: API 호출 전 로그
      console.log('API 호출 시작:', {
        session_id: sessionId,
        user_message: userMessage,
        api_url: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      });
      
      // API 호출
      const response = await chatApi.sendMessage({
        session_id: sessionId,
        user_message: userMessage,
      });
      
      console.log('API 응답 받음:', response);

      // AI 응답 추가
      addMessage('assistant', response.ai_message, response);

      // 상담원 연결이 필요한 경우 알림
      if (response.suggested_action === 'HANDOVER') {
        // 자동으로 상담원 이관 요청할지, 아니면 버튼만 표시할지 결정
        // 여기서는 버튼만 표시하도록 함
      }
    } catch (error: any) {
      console.error('메시지 전송 실패:', error);
      console.error('에러 상세:', {
        message: error?.message,
        code: error?.code,
        response: error?.response?.data,
        status: error?.response?.status,
        config: error?.config
      });
      
      // 더 자세한 에러 메시지 표시
      let errorMessage = '죄송합니다. 메시지 전송 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
      
      if (error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')) {
        errorMessage = '응답 생성에 시간이 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.';
      } else if (error?.code === 'ERR_NETWORK' || error?.message?.includes('Network Error')) {
        errorMessage = '백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.';
        console.error('네트워크 오류 - 백엔드 서버 확인 필요: http://localhost:8000');
      } else if (error?.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error?.message) {
        // 타임아웃 오류는 사용자 친화적인 메시지로 변경
        if (error.message.includes('timeout')) {
          errorMessage = '응답 생성에 시간이 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.';
        } else {
          errorMessage = `오류: ${error.message}`;
        }
      }
      
      addMessage('assistant', errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, addMessage]);

  const handleRequestHandover = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await chatApi.requestHandover({
        session_id: sessionId,
        trigger_reason: 'USER_REQUEST',
      });
      setHandoverData(response);
    } catch (error) {
      console.error('상담원 이관 요청 실패:', error);
      alert('상담원 이관 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const handleCloseModal = useCallback(() => {
    setHandoverData(null);
  }, []);

  const handleResetSession = useCallback(() => {
    if (window.confirm('새로운 상담을 시작하시겠습니까? 현재 대화 내용이 초기화됩니다.')) {
      resetSessionId();
      setMessages([]);
      window.location.reload();
    }
  }, []);

  return (
    <div className="app">
      <ChatWindow
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        onRequestHandover={handleRequestHandover}
      />
      {handoverData && (
        <HandoverModal data={handoverData} onClose={handleCloseModal} />
      )}
      <div className="session-info">
        <span>세션: {sessionId}</span>
        <button onClick={handleResetSession} className="reset-button">
          새 상담 시작
        </button>
      </div>
    </div>
  );
}

export default App;

