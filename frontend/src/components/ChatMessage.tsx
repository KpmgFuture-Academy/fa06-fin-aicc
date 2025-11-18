import React from 'react';
import type { Message } from '../types/api';
import './ChatMessage.css';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  
  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-content">
        <div className="message-text">{message.content}</div>
        {!isUser && message.source_documents && message.source_documents.length > 0 && (
          <div className="source-documents">
            <div className="source-title">참고 문서:</div>
            {message.source_documents.map((doc, idx) => (
              <div key={idx} className="source-item">
                {doc.source} (페이지 {doc.page}, 신뢰도: {(doc.score * 100).toFixed(1)}%)
              </div>
            ))}
          </div>
        )}
        {!isUser && message.intent && (
          <div className="message-meta">
            <span className={`intent-badge intent-${message.intent.toLowerCase()}`}>
              {message.intent === 'INFO_REQ' && '정보 요청'}
              {message.intent === 'COMPLAINT' && '민원'}
              {message.intent === 'HUMAN_REQ' && '상담원 연결'}
            </span>
            {message.suggested_action === 'HANDOVER' && (
              <span className="action-badge handover">상담원 연결 필요</span>
            )}
          </div>
        )}
        <div className="message-time">
          {message.timestamp.toLocaleTimeString('ko-KR', { 
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;

