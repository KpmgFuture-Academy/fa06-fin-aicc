import React, { useCallback } from 'react';
import './ChatMessage.css';
import { useTypingEffect } from '../hooks/useTypingEffect';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isVoice?: boolean;
  isAgent?: boolean;  // 인간 상담사 메시지 여부
  isNew?: boolean;    // 새 메시지 여부 (타이핑 효과 적용)
}

interface ChatMessageProps {
  message: Message;
  onTypingComplete?: () => void;  // 타이핑 완료 콜백
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message, onTypingComplete }) => {
  // 메시지 유형 결정: user, ai, agent
  const messageType = message.role === 'user'
    ? 'user'
    : message.isAgent
      ? 'agent'
      : 'ai';

  // 타이핑 효과 적용 (새 메시지일 때만)
  const shouldAnimate = message.isNew === true;

  const { displayedText, isTyping, skipTyping } = useTypingEffect(
    message.content,
    shouldAnimate,
    {
      speed: 120,  // 한 글자당 120ms (TTS 음성 속도와 유사하게 조정)
      onComplete: onTypingComplete,
    }
  );

  // 클릭 시 스킵
  const handleClick = useCallback(() => {
    if (isTyping) {
      skipTyping();
    }
  }, [isTyping, skipTyping]);

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
    <div
      className={`chat-message chat-message--${message.role} chat-message--${messageType}`}
      onClick={handleClick}
      style={{ cursor: isTyping ? 'pointer' : 'default' }}
    >
      <div className="message-label">{getLabel()}</div>
      <div className="message-content">
        {message.isVoice && (
          <span className="voice-indicator">🎤</span>
        )}
        <p>
          {displayedText}
          {isTyping && <span className="typing-cursor">|</span>}
        </p>
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
