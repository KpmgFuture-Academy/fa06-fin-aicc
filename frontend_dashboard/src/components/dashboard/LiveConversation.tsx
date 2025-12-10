import React, { useEffect, useRef } from 'react';
import styled from 'styled-components';
import { theme } from '../../styles/GlobalStyles';
import { liveConversation } from '../../data/dummyData';

const Container = styled.div`
  background-color: ${theme.colors.white};
  border-radius: 12px;
  box-shadow: ${theme.shadows.card};
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background-color: ${theme.colors.secondary};
  color: ${theme.colors.white};
`;

const HeaderTitle = styled.h3`
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const LiveIndicator = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background-color: ${theme.colors.alert};
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;

  &::before {
    content: '';
    width: 8px;
    height: 8px;
    background-color: white;
    border-radius: 50%;
    animation: blink 1s infinite;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
`;

const ConversationArea = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background-color: #FAFAFA;
`;

const MessageGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const MessageWrapper = styled.div<{ align: 'left' | 'right' | 'center' }>`
  display: flex;
  flex-direction: column;
  align-items: ${props => {
    switch (props.align) {
      case 'left': return 'flex-start';
      case 'right': return 'flex-end';
      case 'center': return 'center';
    }
  }};
`;

const SpeakerLabel = styled.span<{ speaker: string }>`
  font-size: 11px;
  font-weight: 500;
  margin-bottom: 4px;
  color: ${props => {
    switch (props.speaker) {
      case 'customer': return theme.colors.primary;
      case 'agent': return '#1565C0';
      case 'bot': return '#7B1FA2';
      default: return theme.colors.textLight;
    }
  }};
`;

const MessageBubble = styled.div<{ speaker: string }>`
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.5;

  ${props => {
    switch (props.speaker) {
      case 'customer':
        return `
          background-color: ${theme.colors.primary};
          color: white;
          border-bottom-right-radius: 4px;
        `;
      case 'agent':
        return `
          background-color: #E3F2FD;
          color: #1565C0;
          border-bottom-left-radius: 4px;
        `;
      case 'bot':
        return `
          background-color: #F3E5F5;
          color: #7B1FA2;
          border-bottom-left-radius: 4px;
        `;
      case 'system':
        return `
          background-color: ${theme.colors.warning}20;
          color: ${theme.colors.warning};
          border-radius: 8px;
          font-size: 12px;
          padding: 8px 16px;
        `;
      default:
        return `
          background-color: ${theme.colors.background};
          color: ${theme.colors.text};
        `;
    }
  }}
`;

const Timestamp = styled.span`
  font-size: 10px;
  color: ${theme.colors.textLight};
  margin-top: 4px;
`;

const InputArea = styled.div`
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid ${theme.colors.border};
  background-color: ${theme.colors.white};
`;

const MessageInput = styled.input`
  flex: 1;
  padding: 12px 16px;
  border: 1px solid ${theme.colors.border};
  border-radius: 24px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;

  &:focus {
    border-color: ${theme.colors.primary};
  }

  &::placeholder {
    color: ${theme.colors.textLight};
  }
`;

const SendButton = styled.button`
  padding: 12px 24px;
  background-color: ${theme.colors.primary};
  color: white;
  border-radius: 24px;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s;

  &:hover {
    background-color: ${theme.colors.primaryDark};
  }
`;

const getSpeakerLabel = (speaker: string) => {
  switch (speaker) {
    case 'customer': return '고객';
    case 'agent': return '상담원';
    case 'bot': return 'AI 봇';
    case 'system': return '시스템';
    default: return speaker;
  }
};

const getMessageAlign = (speaker: string): 'left' | 'right' | 'center' => {
  switch (speaker) {
    case 'customer': return 'right';
    case 'system': return 'center';
    default: return 'left';
  }
};

const LiveConversation: React.FC = () => {
  const conversationEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  return (
    <Container>
      <Header>
        <HeaderTitle>
          실시간 상담 내역
        </HeaderTitle>
        <LiveIndicator>LIVE</LiveIndicator>
      </Header>

      <ConversationArea>
        <MessageGroup>
          {liveConversation.map(msg => (
            <MessageWrapper key={msg.id} align={getMessageAlign(msg.speaker)}>
              {msg.speaker !== 'system' && (
                <SpeakerLabel speaker={msg.speaker}>
                  {getSpeakerLabel(msg.speaker)}
                </SpeakerLabel>
              )}
              <MessageBubble speaker={msg.speaker}>
                {msg.message}
              </MessageBubble>
              <Timestamp>{msg.timestamp}</Timestamp>
            </MessageWrapper>
          ))}
          <div ref={conversationEndRef} />
        </MessageGroup>
      </ConversationArea>

      <InputArea>
        <MessageInput
          type="text"
          placeholder="메시지를 입력하세요..."
        />
        <SendButton>전송</SendButton>
      </InputArea>
    </Container>
  );
};

export default LiveConversation;
