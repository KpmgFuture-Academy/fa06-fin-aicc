import React from 'react';
import styled from 'styled-components';
import { theme } from '../../styles/GlobalStyles';
import { aiSummary, kmsDocuments } from '../../data/dummyData';

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

const CardHeader = styled.div<{ variant?: 'primary' | 'success' | 'info' }>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background-color: ${props => {
    switch (props.variant) {
      case 'success': return theme.colors.success;
      case 'info': return '#2196F3';
      default: return theme.colors.primary;
    }
  }};
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

const SummaryText = styled.p`
  font-size: 14px;
  line-height: 1.8;
  color: ${theme.colors.text};
  white-space: pre-line;
  margin: 0;
  padding: 16px;
  background-color: ${theme.colors.background};
  border-radius: 8px;
  border-left: 3px solid ${theme.colors.primary};
`;

const SentimentSection = styled.div`
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const SentimentLabel = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
`;

const SentimentBadge = styled.span<{ sentiment: string }>`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  background-color: ${props => {
    switch (props.sentiment) {
      case 'positive': return '#E8F5E9';
      case 'negative': return '#FFEBEE';
      default: return '#FFF3E0';
    }
  }};
  color: ${props => {
    switch (props.sentiment) {
      case 'positive': return '#2E7D32';
      case 'negative': return '#C62828';
      default: return '#EF6C00';
    }
  }};
`;

const KeywordSection = styled.div`
  margin-top: 16px;
`;

const KeywordLabel = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
  display: block;
  margin-bottom: 8px;
`;

const KeywordList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const KeywordTag = styled.span`
  background-color: ${theme.colors.primary}15;
  color: ${theme.colors.primary};
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
`;

const IntentSection = styled.div`
  margin-top: 16px;
  padding: 16px;
  background-color: #E3F2FD;
  border-radius: 8px;
`;

const IntentHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
`;

const IntentLabel = styled.span`
  font-size: 12px;
  color: #1565C0;
`;

const IntentValue = styled.span`
  font-size: 16px;
  font-weight: 600;
  color: #1565C0;
`;

const ConfidenceBar = styled.div`
  height: 6px;
  background-color: rgba(21, 101, 192, 0.2);
  border-radius: 3px;
  overflow: hidden;
`;

const ConfidenceFill = styled.div<{ confidence: number }>`
  height: 100%;
  width: ${props => props.confidence * 100}%;
  background-color: #1565C0;
  border-radius: 3px;
`;

const ConfidenceText = styled.span`
  font-size: 11px;
  color: #1565C0;
  margin-top: 4px;
  display: block;
  text-align: right;
`;

const CollectedInfoGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
`;

const CollectedInfoItem = styled.div`
  padding: 12px;
  background-color: ${theme.colors.background};
  border-radius: 8px;
`;

const CollectedInfoKey = styled.span`
  font-size: 11px;
  color: ${theme.colors.textLight};
  display: block;
  margin-bottom: 4px;
`;

const CollectedInfoValue = styled.span`
  font-size: 13px;
  font-weight: 500;
  color: ${theme.colors.secondary};
`;

const KMSList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const KMSItem = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: ${theme.colors.background};
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: ${theme.shadows.card};
    transform: translateX(4px);
  }
`;

const KMSInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const KMSTitle = styled.span`
  font-size: 14px;
  font-weight: 500;
  color: ${theme.colors.text};
`;

const KMSCategory = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
`;

const KMSRelevance = styled.div`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
`;

const RelevanceValue = styled.span`
  font-size: 14px;
  font-weight: 600;
  color: ${theme.colors.primary};
`;

const RelevanceLabel = styled.span`
  font-size: 10px;
  color: ${theme.colors.textLight};
`;

const getSentimentText = (sentiment: string) => {
  switch (sentiment) {
    case 'positive': return '긍정';
    case 'negative': return '부정';
    default: return '중립';
  }
};

const getSentimentEmoji = (sentiment: string) => {
  switch (sentiment) {
    case 'positive': return '😊';
    case 'negative': return '😞';
    default: return '😐';
  }
};

const AISummary: React.FC = () => {
  return (
    <Container>
      {/* AI 상담 요약 */}
      <Card>
        <CardHeader variant="primary">
          <CardTitle>AI 상담 요약</CardTitle>
          <CardBadge>보이스봇</CardBadge>
        </CardHeader>
        <CardBody>
          <SummaryText>{aiSummary.summary}</SummaryText>

          <SentimentSection>
            <SentimentLabel>고객 감정:</SentimentLabel>
            <SentimentBadge sentiment={aiSummary.customerSentiment}>
              {getSentimentEmoji(aiSummary.customerSentiment)}
              {getSentimentText(aiSummary.customerSentiment)}
            </SentimentBadge>
          </SentimentSection>

          <IntentSection>
            <IntentHeader>
              <IntentLabel>의도 분류</IntentLabel>
              <IntentValue>{aiSummary.intentClassification}</IntentValue>
            </IntentHeader>
            <ConfidenceBar>
              <ConfidenceFill confidence={aiSummary.confidence} />
            </ConfidenceBar>
            <ConfidenceText>신뢰도: {(aiSummary.confidence * 100).toFixed(0)}%</ConfidenceText>
          </IntentSection>

          <KeywordSection>
            <KeywordLabel>핵심 키워드</KeywordLabel>
            <KeywordList>
              {aiSummary.keywords.map((keyword, index) => (
                <KeywordTag key={index}>{keyword}</KeywordTag>
              ))}
            </KeywordList>
          </KeywordSection>
        </CardBody>
      </Card>

      {/* 수집된 정보 */}
      <Card>
        <CardHeader variant="success">
          <CardTitle>수집된 정보</CardTitle>
          <CardBadge>자동 추출</CardBadge>
        </CardHeader>
        <CardBody>
          <CollectedInfoGrid>
            {Object.entries(aiSummary.collectedInfo).map(([key, value]) => (
              <CollectedInfoItem key={key}>
                <CollectedInfoKey>
                  {key === 'inquiryType' && '문의 유형'}
                  {key === 'requestedLimit' && '희망 한도'}
                  {key === 'currentLimit' && '현재 한도'}
                  {key === 'documentReady' && '서류 준비'}
                </CollectedInfoKey>
                <CollectedInfoValue>{value}</CollectedInfoValue>
              </CollectedInfoItem>
            ))}
          </CollectedInfoGrid>
        </CardBody>
      </Card>

      {/* KMS 추천 문서 */}
      <Card>
        <CardHeader variant="info">
          <CardTitle>KMS 추천 문서</CardTitle>
          <CardBadge>{kmsDocuments.length}건</CardBadge>
        </CardHeader>
        <CardBody>
          <KMSList>
            {kmsDocuments.map(doc => (
              <KMSItem key={doc.id}>
                <KMSInfo>
                  <KMSTitle>{doc.title}</KMSTitle>
                  <KMSCategory>{doc.category}</KMSCategory>
                </KMSInfo>
                <KMSRelevance>
                  <RelevanceValue>{(doc.relevance * 100).toFixed(0)}%</RelevanceValue>
                  <RelevanceLabel>관련도</RelevanceLabel>
                </KMSRelevance>
              </KMSItem>
            ))}
          </KMSList>
        </CardBody>
      </Card>
    </Container>
  );
};

export default AISummary;
