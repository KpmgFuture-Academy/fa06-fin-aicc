import React, { useState, useCallback, useEffect, useRef } from 'react';
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
  const [isHandoverMode, setIsHandoverMode] = useState(false);
  const lastMessageIdRef = useRef<number | undefined>(undefined);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

    // 상담원 연결 모드일 때는 AI API 호출하지 않고 메시지만 DB에 저장
    if (isHandoverMode) {
      console.log('[상담원 연결 모드] AI API 호출 생략, 메시지 DB 저장만 수행');
      try {
        // 고객 메시지를 DB에 저장 (상담원이 볼 수 있도록)
        await chatApi.sendCustomerMessage(sessionId, userMessage);
      } catch (error) {
        console.error('고객 메시지 저장 실패:', error);
      }
      return; // AI 응답 없이 종료
    }

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

      // 상담원 연결이 필요한 경우 핸드오버 모드 활성화
      // info_collection_complete가 true일 때만 활성화 (정보 수집 완료 후)
      if (response.suggested_action === 'HANDOVER' && response.info_collection_complete) {
        setIsHandoverMode(true);
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
  }, [sessionId, addMessage, isHandoverMode]);

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

  // 폴링: 상담원 메시지 수신 (HANDOVER 모드일 때만)
  useEffect(() => {
    if (!isHandoverMode) {
      // HANDOVER 모드가 아니면 폴링 중지
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    console.log('[폴링 시작] 상담원 연결 모드 - 2초마다 메시지 확인');

    const pollForMessages = async () => {
      try {
        // after_handover=true 명시적으로 전달하여 HANDOVER 이후 메시지만 조회
        const newMessages = await chatApi.pollMessages(sessionId, lastMessageIdRef.current, true);

        console.log('[폴링] 조회된 메시지:', newMessages.length, '개');

        // 새 메시지가 있으면 화면에 추가
        for (const msg of newMessages) {
          // 상담원 메시지만 추가 (user가 보낸 메시지는 이미 화면에 있음)
          if (msg.role === 'assistant') {
            console.log('[폴링] 상담원 메시지 발견:', msg.id, msg.message.substring(0, 30));

            // setMessages 내부에서 중복 확인 (함수형 업데이트)
            setMessages(prev => {
              const alreadyExists = prev.some(m => m.id === `db_${msg.id}`);
              if (alreadyExists) {
                return prev;
              }
              const newMessage: Message = {
                id: `db_${msg.id}`,
                role: 'assistant',
                content: msg.message,
                timestamp: new Date(msg.created_at),
              };
              return [...prev, newMessage];
            });
          }
          // 마지막 메시지 ID 업데이트
          lastMessageIdRef.current = Math.max(lastMessageIdRef.current || 0, msg.id);
        }
      } catch (error) {
        console.error('[폴링 오류] 메시지 조회 실패:', error);
      }
    };

    // 즉시 한번 실행
    pollForMessages();

    // 2초마다 폴링
    pollingIntervalRef.current = setInterval(pollForMessages, 2000);

    // 클린업
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isHandoverMode, sessionId]); // messages 의존성 제거 - 무한 루프 방지

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

