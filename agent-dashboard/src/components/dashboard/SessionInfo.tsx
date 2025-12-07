import React from 'react';
import styled from 'styled-components';
import { theme } from '../../styles/GlobalStyles';
import { currentSession, recommendedScripts, recentHistory } from '../../data/dummyData';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const Card = styled.div`
  background-color: ${theme.colors.white};
  border-radius: 12px;
  box-shadow: ${theme.shadows.card};
  overflow: hidden;
`;

const CardHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background-color: ${theme.colors.primary};
  color: ${theme.colors.white};
`;

const CardTitle = styled.h3`
  font-size: 16px;
  font-weight: 600;
  margin: 0;
`;

const CardBadge = styled.span`
  background-color: rgba(255, 255, 255, 0.2);
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
`;

const CardBody = styled.div`
  padding: 20px;
`;

const InfoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
`;

const InfoItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const InfoLabel = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
`;

const InfoValue = styled.span`
  font-size: 14px;
  font-weight: 500;
  color: ${theme.colors.secondary};
`;

const IVRPath = styled.div`
  margin-top: 16px;
  padding: 12px;
  background-color: ${theme.colors.background};
  border-radius: 8px;
`;

const IVRLabel = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
  display: block;
  margin-bottom: 4px;
`;

const IVRValue = styled.span`
  font-size: 14px;
  color: ${theme.colors.primary};
  font-weight: 500;
`;

const ScriptList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ScriptItem = styled.div`
  padding: 16px;
  background-color: ${theme.colors.background};
  border-radius: 8px;
  border-left: 3px solid ${theme.colors.primary};
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: ${theme.shadows.card};
    transform: translateX(4px);
  }
`;

const ScriptTitle = styled.h4`
  font-size: 14px;
  font-weight: 600;
  color: ${theme.colors.primary};
  margin: 0 0 8px 0;
`;

const ScriptContent = styled.p`
  font-size: 13px;
  color: ${theme.colors.text};
  margin: 0;
  line-height: 1.6;
`;

const HistoryTable = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const HistoryTh = styled.th`
  text-align: left;
  padding: 12px 8px;
  font-size: 12px;
  font-weight: 600;
  color: ${theme.colors.textLight};
  border-bottom: 1px solid ${theme.colors.border};
`;

const HistoryTd = styled.td`
  padding: 12px 8px;
  font-size: 13px;
  color: ${theme.colors.text};
  border-bottom: 1px solid ${theme.colors.border};
`;

const ChannelBadge = styled.span<{ channel: string }>`
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background-color: ${props => {
    switch (props.channel) {
      case '전화': return '#E3F2FD';
      case '앱': return '#E8F5E9';
      case '웹': return '#FFF3E0';
      default: return theme.colors.background;
    }
  }};
  color: ${props => {
    switch (props.channel) {
      case '전화': return '#1565C0';
      case '앱': return '#2E7D32';
      case '웹': return '#EF6C00';
      default: return theme.colors.text;
    }
  }};
`;

const TransferReason = styled.div`
  margin-top: 16px;
  padding: 12px;
  background-color: #FFF3E0;
  border-radius: 8px;
  border-left: 3px solid ${theme.colors.warning};
`;

const TransferLabel = styled.span`
  font-size: 12px;
  color: ${theme.colors.warning};
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
`;

const TransferValue = styled.span`
  font-size: 14px;
  color: ${theme.colors.text};
`;

const SessionInfo: React.FC = () => {
  return (
    <Container>
      {/* 현재 세션 정보 */}
      <Card>
        <CardHeader>
          <CardTitle>현재 세션 정보</CardTitle>
          <CardBadge>{currentSession.channel}</CardBadge>
        </CardHeader>
        <CardBody>
          <InfoGrid>
            <InfoItem>
              <InfoLabel>콜 ID</InfoLabel>
              <InfoValue>{currentSession.callId}</InfoValue>
            </InfoItem>
            <InfoItem>
              <InfoLabel>발신 번호</InfoLabel>
              <InfoValue>{currentSession.callerNumber}</InfoValue>
            </InfoItem>
            <InfoItem>
              <InfoLabel>시작 시간</InfoLabel>
              <InfoValue>{currentSession.startTime}</InfoValue>
            </InfoItem>
            <InfoItem>
              <InfoLabel>통화 시간</InfoLabel>
              <InfoValue>{currentSession.duration}</InfoValue>
            </InfoItem>
          </InfoGrid>

          <IVRPath>
            <IVRLabel>IVR 경로</IVRLabel>
            <IVRValue>{currentSession.ivrPath}</IVRValue>
          </IVRPath>

          <TransferReason>
            <TransferLabel>이관 사유</TransferLabel>
            <TransferValue>{currentSession.transferReason}</TransferValue>
          </TransferReason>
        </CardBody>
      </Card>

      {/* 추천 스크립트 */}
      <Card>
        <CardHeader>
          <CardTitle>추천 스크립트</CardTitle>
          <CardBadge>AI 추천</CardBadge>
        </CardHeader>
        <CardBody>
          <ScriptList>
            {recommendedScripts.map(script => (
              <ScriptItem key={script.id}>
                <ScriptTitle>{script.title}</ScriptTitle>
                <ScriptContent>{script.content}</ScriptContent>
              </ScriptItem>
            ))}
          </ScriptList>
        </CardBody>
      </Card>

      {/* 최근 상담 이력 */}
      <Card>
        <CardHeader>
          <CardTitle>최근 3개월 상담 이력</CardTitle>
          <CardBadge>{recentHistory.length}건</CardBadge>
        </CardHeader>
        <CardBody>
          <HistoryTable>
            <thead>
              <tr>
                <HistoryTh>일자</HistoryTh>
                <HistoryTh>채널</HistoryTh>
                <HistoryTh>유형</HistoryTh>
                <HistoryTh>요약</HistoryTh>
              </tr>
            </thead>
            <tbody>
              {recentHistory.map((item, index) => (
                <tr key={index}>
                  <HistoryTd>{item.date}</HistoryTd>
                  <HistoryTd>
                    <ChannelBadge channel={item.channel}>{item.channel}</ChannelBadge>
                  </HistoryTd>
                  <HistoryTd>{item.category}</HistoryTd>
                  <HistoryTd>{item.summary}</HistoryTd>
                </tr>
              ))}
            </tbody>
          </HistoryTable>
        </CardBody>
      </Card>
    </Container>
  );
};

export default SessionInfo;
