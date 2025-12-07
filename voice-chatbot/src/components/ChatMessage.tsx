import React from 'react';
import './ChatMessage.css';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isVoice?: boolean;
}

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  return (
    <div className={`chat-message chat-message--${message.role}`}>
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
