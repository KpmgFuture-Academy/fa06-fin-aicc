import React from 'react';
import './ChatMessage.css';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isVoice?: boolean;
  isAgent?: boolean;  // 인간 상담사 메시지 여부
}

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  // 메시지 유형 결정: user, ai, agent
  const messageType = message.role === 'user'
    ? 'user'
    : message.isAgent
      ? 'agent'
      : 'ai';

  // 라벨 표시
  const getLabel = () => {
    switch (messageType) {
      case 'user':
        return '고객';
      case 'agent':
        return '상담사';
      case 'ai':
        return 'AI';
      default:
        return '';
    }
  };

  return (
    <div className={`chat-message chat-message--${message.role} chat-message--${messageType}`}>
      <div className="message-label">{getLabel()}</div>
      <div className="message-content">
        {message.isVoice && (
          <span className="voice-indicator">🎤</span>
        )}
        <p>{message.content}</p>
      </div>
      <span className="message-time">
        {message.timestamp.toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
        })}
      </span>
    </div>
  );
};

export default ChatMessage;
