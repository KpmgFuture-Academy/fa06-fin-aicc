import React, { useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import type { Message } from '../types/api';
import './ChatWindow.css';

interface ChatWindowProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
  onRequestHandover?: () => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  onSendMessage,
  isLoading = false,
  onRequestHandover,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 새 메시지가 추가될 때 스크롤
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="chat-header-content">
          <h1>Bank AICC 상담 챗봇</h1>
          <p>AI 기반 고객 상담 서비스</p>
        </div>
        {onRequestHandover && (
          <button className="handover-button" onClick={onRequestHandover}>
            상담원 연결
          </button>
        )}
      </div>

      <div className="chat-messages" ref={messagesContainerRef}>
        {messages.length === 0 ? (
          <div className="welcome-message">
            <div className="welcome-icon">💬</div>
            <h2>안녕하세요! 무엇을 도와드릴까요?</h2>
            <p>궁금한 사항을 자유롭게 물어보세요.</p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
        {isLoading && (
          <div className="loading-message">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <ChatInput
        onSendMessage={onSendMessage}
        disabled={isLoading}
        placeholder={isLoading ? '답변을 기다리는 중...' : '메시지를 입력하세요...'}
      />
    </div>
  );
};

export default ChatWindow;

