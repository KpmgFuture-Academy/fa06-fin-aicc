import React, { useState, useEffect, useRef, useCallback } from 'react';
import styled from 'styled-components';
import { theme } from '../styles/GlobalStyles';
import {
  analyzeHandover,
  getCurrentTimestamp,
  getHandoverSessions,
  getSessionMessages,
  sendAgentMessage,
  closeSession,
  acceptSession,
  getClosedSessions,
  getAllSessionMessages,
  transcribeAudio,
  Message,
  HandoverSession,
  HandoverAnalysisResult,
  DBMessage
} from '../services/api';
import { useAudioRecorder } from '../hooks/useAudioRecorder';

const Container = styled.div`
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
`;

const DashboardHeader = styled.div`
  color: white;
  padding: 8px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const DashboardTitle = styled.h1`
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
`;

const DashboardSubtitle = styled.p`
  font-size: 1.5rem;
  font-weight: 700;
  opacity: 0.9;
  margin: 0;
  margin-right: 16px;
`;

const TopSection = styled.div`
  display: flex;
  background-color: ${theme.colors.white};
  border: 3px solid #5a4fcf;
`;

// 왼쪽: 상담 연결 + 상태 표시
const ConnectionStatusArea = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-right: 1px solid #ddd;
  min-width: 180px;
`;

const ConnectionTitle = styled.div`
  font-size: 18px;
  font-weight: 700;
  color: #333;
`;

const StatusIndicator = styled.div<{ $isConnected: boolean; $isClosed?: boolean }>`
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: ${props => {
    if (props.$isClosed) return '#9E9E9E';  // 회색: 종료됨
    return props.$isConnected ? '#4CAF50' : '#f44336';  // 초록: 연결, 빨강: 대기
  }};
  box-shadow: 0 0 8px ${props => {
    if (props.$isClosed) return 'rgba(158, 158, 158, 0.5)';
    return props.$isConnected ? 'rgba(76, 175, 80, 0.5)' : 'rgba(244, 67, 54, 0.5)';
  }};
`;

// 중앙: Slot Filling 정보
const SlotFillingArea = styled.div`
  flex: 1;
  padding: 8px 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 16px;
  border-right: 1px solid #ddd;
`;

const SlotItem = styled.div`
  display: flex;
  gap: 8px;
`;

const SlotLabel = styled.span`
  font-size: 13px;
  color: #666;
  min-width: 80px;
`;

const SlotValue = styled.span`
  font-size: 13px;
  font-weight: 500;
  color: #333;
`;

// 오른쪽: 시간 정보
const TimeInfoArea = styled.div`
  padding: 8px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 160px;
`;

const TimeItem = styled.div`
  display: flex;
  gap: 8px;
`;

const TimeLabel = styled.span`
  font-size: 13px;
  color: #666;
  min-width: 70px;
`;

const TimeValue = styled.span`
  font-size: 13px;
  font-weight: 500;
  color: #333;
`;

// 세션 선택 드롭다운 영역
const SessionSelectArea = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
`;

const SessionSelectLabel = styled.span`
  font-size: 13px;
  color: #666;
`;

const SessionSelect = styled.select`
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  min-width: 300px;
  cursor: pointer;

  &:focus {
    outline: none;
    border-color: ${theme.colors.primary};
  }
`;

const NoSessionText = styled.span`
  color: #999;
  font-size: 12px;
`;

// 세션 수량 표시
const SessionCountArea = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: 24px;
  padding-left: 24px;
  border-left: 1px solid #ddd;
`;

const SessionCountItem = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
`;

const SessionCountLabel = styled.span`
  font-size: 14px;
  font-weight: 500;
  color: #333;
`;

const SessionCountValue = styled.span<{ $isAlert?: boolean }>`
  font-size: 15px;
  font-weight: 600;
  color: ${props => props.$isAlert ? '#f44336' : '#333'};
`;

// 사이드바: 종료된 상담 기록
const Sidebar = styled.div<{ $isOpen: boolean }>`
  position: fixed;
  right: ${props => props.$isOpen ? '0' : '-320px'};
  top: 0;
  width: 320px;
  height: 100vh;
  background-color: #fff;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.15);
  transition: right 0.3s ease;
  z-index: 1000;
  display: flex;
  flex-direction: column;
`;

const SidebarHeader = styled.div`
  padding: 16px;
  background-color: #5a4fcf;
  color: white;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const SidebarCloseButton = styled.button`
  background: none;
  border: none;
  color: white;
  font-size: 20px;
  cursor: pointer;
  padding: 0 8px;

  &:hover {
    opacity: 0.8;
  }
`;

const SidebarContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 12px;
`;

const ClosedSessionItem = styled.div<{ isSelected?: boolean }>`
  padding: 12px;
  border: 1px solid ${props => props.isSelected ? '#5a4fcf' : '#ddd'};
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  background-color: ${props => props.isSelected ? '#f0efff' : '#fff'};

  &:hover {
    background-color: #f5f5f5;
    border-color: #5a4fcf;
  }
`;

const ClosedSessionDate = styled.div`
  font-size: 11px;
  color: #666;
  margin-bottom: 4px;
`;

const ClosedSessionName = styled.div`
  font-size: 14px;
  font-weight: 500;
  color: #333;
`;

const ClosedSessionType = styled.div`
  font-size: 12px;
  color: #888;
  margin-top: 4px;
`;

const SidebarToggleButton = styled.button`
  background-color: #5a4fcf;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  margin-left: auto;
  margin-right: 8px;

  &:hover {
    background-color: #4a3fbf;
  }
`;

// 마이크 버튼 스타일
const MicButton = styled.button<{ $isRecording: boolean; $isProcessing?: boolean }>`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  background-color: ${props => {
    if (props.$isProcessing) return '#9e9e9e';
    if (props.$isRecording) return '#f44336';
    return '#4CAF50';
  }};
  color: white;
  border: none;
  border-radius: 20px;
  cursor: ${props => props.$isProcessing ? 'wait' : 'pointer'};
  font-size: 13px;
  font-weight: 500;
  margin-left: auto;
  transition: all 0.2s;

  &:hover {
    opacity: ${props => props.$isProcessing ? 1 : 0.9};
  }

  &:disabled {
    background-color: #ccc;
    cursor: not-allowed;
  }

  ${props => props.$isRecording && `
    animation: pulse 1s infinite;
  `}

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
`;

const MicIcon = styled.span`
  font-size: 16px;
`;

const SidebarOverlay = styled.div<{ $isOpen: boolean }>`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.3);
  z-index: 999;
  display: ${props => props.$isOpen ? 'block' : 'none'};
`;

const HistoryChatArea = styled.div`
  margin-top: 12px;
  padding: 12px;
  background-color: #f9f9f9;
  border-radius: 8px;
  max-height: 400px;
  overflow-y: auto;
`;

const HistoryMessage = styled.div<{ isUser: boolean }>`
  margin-bottom: 8px;
  text-align: ${props => props.isUser ? 'right' : 'left'};
`;

const HistoryBubble = styled.div<{ isUser: boolean }>`
  display: inline-block;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  max-width: 85%;
  background-color: ${props => props.isUser ? '#5a4fcf' : '#e0e0e0'};
  color: ${props => props.isUser ? 'white' : '#333'};
`;

const HistoryTime = styled.div`
  font-size: 10px;
  color: #999;
  margin-top: 2px;
`;

const MainContent = styled.div`
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  min-height: 0;
`;

const Section = styled.div`
  display: flex;
  flex-direction: column;
  background-color: ${theme.colors.white};
  border: 1px solid #333;
  min-height: 0;
`;

const SectionHeader = styled.div`
  padding: 12px 16px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const LiveBadge = styled.span`
  background-color: ${theme.colors.alert};
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  animation: pulse 1.5s infinite;

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
`;

const SectionBody = styled.div`
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  min-height: 0;
`;

const ChatArea = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const ChatMessage = styled.div<{ align: 'left' | 'right' | 'center' }>`
  display: flex;
  flex-direction: column;
  align-items: ${props => {
    if (props.align === 'right') return 'flex-end';
    if (props.align === 'center') return 'center';
    return 'flex-start';
  }};
`;

const MessageLabel = styled.span<{ type: string; $isAi?: boolean }>`
  font-size: 11px;
  color: ${props => {
    if (props.type === 'customer') return theme.colors.primary;
    if (props.type === 'agent') {
      // AI 생성 메시지는 보라색, 상담사 직접 메시지는 파란색
      return props.$isAi ? '#7B1FA2' : '#1565C0';
    }
    return '#666';
  }};
  margin-bottom: 3px;
`;

const MessageBubble = styled.div<{ type: string; $isAi?: boolean }>`
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.4;

  ${props => {
    if (props.type === 'customer') {
      return `
        background-color: ${theme.colors.primary};
        color: white;
      `;
    }
    if (props.type === 'agent') {
      // AI 생성 메시지는 연보라색, 상담사 직접 메시지는 연파란색
      if (props.$isAi) {
        return `
          background-color: #F3E5F5;
          color: #333;
        `;
      }
      return `
        background-color: #E3F2FD;
        color: #333;
      `;
    }
    if (props.type === 'system') {
      return `
        background-color: #FFF3E0;
        color: #EF6C00;
        font-size: 11px;
        padding: 6px 12px;
      `;
    }
    return `
      background-color: #f5f5f5;
      color: #333;
    `;
  }}
`;

const MessageTime = styled.span`
  font-size: 10px;
  color: #999;
  margin-top: 3px;
`;

const InputArea = styled.div`
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #ddd;
  background-color: #f9f9f9;
`;

const ChatInput = styled.input`
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 20px;
  font-size: 13px;
  outline: none;

  &:focus {
    border-color: ${theme.colors.primary};
  }

  &:disabled {
    background-color: #eee;
  }
`;

const SendButton = styled.button`
  padding: 10px 20px;
  background-color: ${theme.colors.primary};
  color: white;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;

  &:hover {
    background-color: ${theme.colors.primaryDark};
  }

  &:disabled {
    background-color: #ccc;
    cursor: not-allowed;
  }
`;

const CloseSessionButton = styled.button`
  padding: 10px 20px;
  background-color: #f44336;
  color: white;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;

  &:hover {
    background-color: #d32f2f;
  }

  &:disabled {
    background-color: #ccc;
    cursor: not-allowed;
  }
`;

const AcceptSessionButton = styled.button`
  padding: 10px 20px;
  background-color: #4CAF50;
  color: white;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  margin-left: 12px;

  &:hover {
    background-color: #45a049;
  }

  &:disabled {
    background-color: #ccc;
    cursor: not-allowed;
  }
`;

const SummaryBlock = styled.div`
  margin-bottom: 16px;

  &:last-child {
    margin-bottom: 0;
  }
`;

const SummaryTitle = styled.h4`
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid #eee;
`;

const SummaryText = styled.p`
  font-size: 13px;
  line-height: 1.5;
  color: #333;
  margin: 0;
  white-space: pre-line;
  background-color: #f9f9f9;
  padding: 10px;
  border-radius: 6px;
`;

const InfoGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
`;

const InfoBox = styled.div`
  padding: 10px;
  background-color: #f0f7ff;
  border-radius: 6px;
  border-left: 3px solid ${theme.colors.primary};
`;

const InfoBoxValue = styled.div`
  font-size: 13px;
  font-weight: 500;
  color: #333;
`;

const KeywordList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
`;

const Keyword = styled.span`
  padding: 4px 10px;
  background-color: ${theme.colors.primary};
  color: white;
  border-radius: 14px;
  font-size: 12px;
`;

const SentimentBadge = styled.span<{ $sentiment: string }>`
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  ${props => {
    switch (props.$sentiment) {
      case 'POSITIVE':
        return 'background-color: #E8F5E9; color: #2E7D32;';
      case 'NEGATIVE':
        return 'background-color: #FFEBEE; color: #C62828;';
      default:
        return 'background-color: #FFF3E0; color: #EF6C00;';
    }
  }}
`;

const LoadingText = styled.div`
  text-align: center;
  color: #666;
  padding: 20px;
  font-size: 13px;
`;

const RefreshButton = styled.button<{ $isLoading?: boolean }>`
  padding: 4px 10px;
  font-size: 11px;
  background-color: ${props => props.$isLoading ? '#e0e0e0' : '#f5f5f5'};
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: ${props => props.$isLoading ? 'wait' : 'pointer'};
  opacity: ${props => props.$isLoading ? 0.7 : 1};
  transition: all 0.2s;

  &:hover {
    background-color: #e0e0e0;
  }

  &:disabled {
    cursor: wait;
    opacity: 0.7;
  }
`;

const getSentimentText = (sentiment: string) => {
  switch (sentiment) {
    case 'POSITIVE': return '긍정';
    case 'NEGATIVE': return '부정';
    default: return '중립';
  }
};

// 슬롯 라벨 매핑 (영문 키 → 한글 라벨)
const SLOT_LABELS: Record<string, string> = {
  card_last_4_digits: '카드 뒤 4자리',
  card_type: '카드 종류',
  loss_date: '분실 일시',
  loss_location: '분실 장소',
  request_type: '요청 유형',
  fraud_date: '부정사용 일시',
  fraud_amount: '부정사용 금액',
  fraud_merchant: '부정사용 가맹점',
  requested_limit: '희망 한도',
  purpose: '상향 목적',
  transaction_date: '거래 일시',
  transaction_amount: '거래 금액',
  merchant_name: '가맹점명',
  receipt_number: '접수 번호',
  receipt_date: '접수 일시',
  payment_month: '결제월',
  desired_payment_date: '희망 결제일',
  new_bank: '변경할 은행',
  new_account_number: '새 계좌번호',
  inquiry_period: '조회 기간',
  change_type: '변경 유형',
  prepay_amount: '선결제 금액',
  error_date: '오류 발생일',
  error_description: '오류 내용',
  auto_payment_service: '자동결제 서비스',
  withdrawal_account: '출금 계좌',
  withdrawal_amount: '출금 금액',
  payment_amount: '결제 금액',
  payment_ratio: '결제 비율',
  desired_loan_amount: '희망 대출 금액',
  desired_amount: '희망 금액',
  repayment_period: '상환 기간',
  repayment_amount: '상환 금액',
  repayment_type: '상환 방식',
  usage_destination: '사용처',
  partner_name: '제휴사명',
  inquiry_type: '문의 유형',
  issue_period: '발급 기간',
  issue_method: '발급 방식',
  reissue_reason: '재발급 사유',
  delivery_address: '배송 주소',
  inquiry_year: '조회 연도',
  business_number: '사업자번호',
  inquiry_detail: '문의 상세',
};

const getSlotLabel = (key: string): string => {
  return SLOT_LABELS[key] || key;
};

const Dashboard: React.FC = () => {
  // 이관 대기 세션 목록
  const [handoverSessions, setHandoverSessions] = useState<HandoverSession[]>([]);
  // 현재 선택된 세션
  const [selectedSession, setSelectedSession] = useState<HandoverSession | null>(null);
  // 대화 메시지
  const [messages, setMessages] = useState<Message[]>([]);
  // 입력 값
  const [inputValue, setInputValue] = useState<string>('');
  // 전송 중
  const [isSending, setIsSending] = useState<boolean>(false);
  // 분석 결과
  const [analysisResult, setAnalysisResult] = useState<HandoverAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  // 새로고침 중
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  // 상담 시간 관련 상태
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  // 상담원이 직접 보낸 메시지 ID 목록 (AI 메시지와 구분용)
  const agentSentMessageIds = useRef<Set<number>>(new Set());
  // 폴링용 마지막 메시지 ID
  const lastMessageIdRef = useRef<number | undefined>(undefined);
  // 핸드오버 수락 시간 (ref로 저장하여 폴링에서 참조)
  const handoverAcceptedAtRef = useRef<Date | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // 사이드바: 종료된 상담 기록
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [closedSessions, setClosedSessions] = useState<HandoverSession[]>([]);
  const [selectedClosedSession, setSelectedClosedSession] = useState<HandoverSession | null>(null);
  const [historyMessages, setHistoryMessages] = useState<DBMessage[]>([]);

  // 음성 녹음 관련
  const { isRecording, startRecording, stopRecording, error: recordingError } = useAudioRecorder();
  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);

  // 세션 수락 관련
  const [isAccepting, setIsAccepting] = useState<boolean>(false);
  const [isSessionAccepted, setIsSessionAccepted] = useState<boolean>(false);

  // 시간 포맷팅 헬퍼
  const formatTime = (date: Date | null): string => {
    if (!date) return '-';
    return date.toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  // 통화 시간 계산
  const calculateDuration = (): string => {
    if (!startTime) return '-';
    const end = endTime || new Date();
    const diffMs = end.getTime() - startTime.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const minutes = Math.floor(diffSec / 60);
    const seconds = diffSec % 60;
    return `${minutes}분 ${seconds}초`;
  };

  // 스크롤 자동
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 이관 대기 세션 목록 조회
  const fetchHandoverSessions = useCallback(async (showLoading = false) => {
    if (showLoading) setIsRefreshing(true);
    try {
      const sessions = await getHandoverSessions();
      setHandoverSessions(sessions);
    } catch (error) {
      console.error('이관 세션 조회 실패:', error);
    } finally {
      if (showLoading) setIsRefreshing(false);
    }
  }, []);

  // 종료된 세션 목록 조회 (사이드바용)
  const fetchClosedSessions = useCallback(async () => {
    try {
      const sessions = await getClosedSessions();
      setClosedSessions(sessions);
    } catch (error) {
      console.error('종료된 세션 조회 실패:', error);
    }
  }, []);

  // 종료된 세션 클릭 시 메시지 로드
  const handleSelectClosedSession = async (session: HandoverSession) => {
    setSelectedClosedSession(session);
    try {
      const messages = await getAllSessionMessages(session.session_id);
      setHistoryMessages(messages);
    } catch (error) {
      console.error('메시지 조회 실패:', error);
      setHistoryMessages([]);
    }
  };

  // 사이드바 열기
  const handleOpenSidebar = () => {
    setIsSidebarOpen(true);
    fetchClosedSessions();
  };

  // 사이드바 닫기
  const handleCloseSidebar = () => {
    setIsSidebarOpen(false);
    setSelectedClosedSession(null);
    setHistoryMessages([]);
  };

  // 초기 로드 + 5분마다 세션 목록 갱신 (폴링 간격 대폭 증가)
  useEffect(() => {
    fetchHandoverSessions();
    fetchClosedSessions();  // 종료된 세션 수량도 초기 로드
    const interval = setInterval(() => {
      fetchHandoverSessions();
      fetchClosedSessions();
    }, 300000); // 30초 -> 5분(300초)으로 대폭 증가
    return () => clearInterval(interval);
  }, [fetchHandoverSessions, fetchClosedSessions]);

  // 세션 선택 시 처리
  const handleSelectSession = async (session: HandoverSession) => {
    // 기존 폴링 중지
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }

    // 이전 종료 상태 초기화
    setIsSessionClosed(false);
    // 수락 상태 초기화
    setIsSessionAccepted(false);

    // 최신 세션 정보 가져오기 (collected_info 포함)
    try {
      const latestSessions = await getHandoverSessions();
      const latestSession = latestSessions.find(s => s.session_id === session.session_id);
      setSelectedSession(latestSession || session);
      // 세션 목록도 업데이트
      setHandoverSessions(latestSessions);
    } catch (error) {
      console.error('최신 세션 정보 조회 실패:', error);
      setSelectedSession(session);
    }
    setMessages([]);
    setAnalysisResult(null);
    lastMessageIdRef.current = undefined;

    // 상담 시작 시간 기록
    setStartTime(new Date());
    setEndTime(null);

    // 상담원이 직접 보낸 메시지 ID 초기화
    agentSentMessageIds.current.clear();

    // 기존 메시지 로드 (HANDOVER 이전 대화 포함 - 전체 대화 표시)
    try {
      const dbMessages = await getSessionMessages(session.session_id, undefined, false);

      // 핸드오버 수락 시간 (세션 정보에서 가져옴)
      const handoverAcceptedAt = session.handover_accepted_at
        ? new Date(session.handover_accepted_at)
        : null;
      // ref에도 저장 (폴링에서 참조용)
      handoverAcceptedAtRef.current = handoverAcceptedAt;

      const converted: Message[] = dbMessages.map((m: DBMessage) => {
        const messageTime = new Date(m.created_at);

        // AI 생성 여부 판단:
        // - user 메시지는 항상 false
        // - assistant 메시지 중 핸드오버 수락 이전은 AI 생성
        // - assistant 메시지 중 핸드오버 수락 이후는 상담사 (AI 아님)
        const isAiGenerated = m.role === 'assistant' && (
          !handoverAcceptedAt || messageTime < handoverAcceptedAt
        );

        return {
          id: m.id,
          speaker: m.role === 'user' ? 'customer' : 'agent',
          message: m.message,
          timestamp: messageTime.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
          }),
          isAiGenerated
        };
      });
      setMessages(converted);

      if (dbMessages.length > 0) {
        lastMessageIdRef.current = Math.max(...dbMessages.map((m: DBMessage) => m.id));
      }

      // 이관 분석 요청 (비동기 - 메시지 로드와 병렬 처리)
      setIsAnalyzing(true);
      analyzeHandover({
        session_id: session.session_id,
        trigger_reason: '상담원 이관 분석'
      }).then(async (handoverResult) => {
        setAnalysisResult(handoverResult.analysis_result);

        // 분석 완료 후 최신 세션 정보 다시 가져오기 (collected_info 갱신)
        try {
          const updatedSessions = await getHandoverSessions();
          const updatedSession = updatedSessions.find(s => s.session_id === session.session_id);
          if (updatedSession) {
            setSelectedSession(updatedSession);
            setHandoverSessions(updatedSessions);
            console.log('세션 정보 갱신 완료:', updatedSession.collected_info);
          }
        } catch (err) {
          console.error('세션 정보 갱신 실패:', err);
        }
      }).catch(error => {
        console.error('이관 분석 실패:', error);
      }).finally(() => {
        setIsAnalyzing(false);
      });

      // 폴링 시작 (2초마다 - 메시지 로드 직후 바로 시작)
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const newMessages = await getSessionMessages(session.session_id, lastMessageIdRef.current, false);
          if (newMessages.length > 0) {
            const newConverted: Message[] = newMessages.map((m: DBMessage) => {
              const messageTime = new Date(m.created_at);
              const handoverAcceptedAt = handoverAcceptedAtRef.current;

              // AI 생성 여부 판단:
              // - user 메시지는 항상 false
              // - 상담원이 직접 보낸 메시지(agentSentMessageIds에 있음)는 false
              // - 핸드오버 수락 이후의 assistant 메시지는 상담사 메시지로 간주 (false)
              // - 그 외는 AI 생성
              const isAiGenerated = m.role === 'assistant' && (
                !agentSentMessageIds.current.has(m.id) &&
                (!handoverAcceptedAt || messageTime < handoverAcceptedAt)
              );

              return {
                id: m.id,
                speaker: m.role === 'user' ? 'customer' : 'agent',
                message: m.message,
                timestamp: messageTime.toLocaleTimeString('ko-KR', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: false
                }),
                isAiGenerated
              };
            });
            setMessages(prev => [...prev, ...newConverted]);
            lastMessageIdRef.current = Math.max(...newMessages.map((m: DBMessage) => m.id));
          }
        } catch (error) {
          console.error('폴링 오류:', error);
        }
      }, 2000); // 2초마다 폴링 (실시간 통신용)

    } catch (error) {
      console.error('메시지 로드 실패:', error);
    }
  };

  // 컴포넌트 언마운트 시 폴링 정리
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  // 메시지 전송 (상담원 → 고객)
  const handleSendMessage = async () => {
    if (!inputValue.trim() || isSending || !selectedSession) return;

    const messageText = inputValue.trim();
    setInputValue('');
    setIsSending(true);

    try {
      const result = await sendAgentMessage(selectedSession.session_id, messageText);

      // 상담원이 직접 보낸 메시지로 기록
      agentSentMessageIds.current.add(result.message_id);

      // 전송 성공 시 바로 화면에 추가
      const newMessage: Message = {
        id: result.message_id,
        speaker: 'agent',
        message: messageText,
        timestamp: getCurrentTimestamp(),
        isAiGenerated: false  // 상담원이 직접 보낸 메시지
      };
      setMessages(prev => [...prev, newMessage]);
      lastMessageIdRef.current = result.message_id;

    } catch (error) {
      console.error('메시지 전송 실패:', error);
      alert('메시지 전송에 실패했습니다.');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 세션 종료 상태 (종료 후에도 정보 유지)
  const [isSessionClosed, setIsSessionClosed] = useState<boolean>(false);

  // 세션 종료 핸들러
  const handleCloseSession = async () => {
    if (!selectedSession) return;

    if (!window.confirm('상담을 종료하시겠습니까?')) return;

    try {
      await closeSession(selectedSession.session_id);

      // 종료 시간 기록
      setEndTime(new Date());

      // 세션 종료 상태 표시
      setIsSessionClosed(true);

      // 폴링 중지
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }

      // 세션 목록 새로고침
      fetchHandoverSessions(true);

      alert('상담이 종료되었습니다. 다른 세션을 선택하거나 새로고침하세요.');
    } catch (error) {
      console.error('세션 종료 실패:', error);
      alert('세션 종료에 실패했습니다.');
    }
  };

  // 세션 수락 핸들러 (상담사가 세션 선택 시 호출)
  const handleAcceptSession = async () => {
    if (!selectedSession || isSessionAccepted) return;

    setIsAccepting(true);
    try {
      await acceptSession(selectedSession.session_id, 'agent_001'); // 임시 상담사 ID
      setIsSessionAccepted(true);
      // 수락 시간 기록 (이후 메시지는 상담사 메시지로 간주)
      handoverAcceptedAtRef.current = new Date();
      console.log('세션 수락 완료:', selectedSession.session_id);

      // 수락 완료 후 분석 정보 로드
      setIsAnalyzing(true);
      try {
        const handoverResult = await analyzeHandover({
          session_id: selectedSession.session_id,
          trigger_reason: '상담원 이관 분석'
        });
        setAnalysisResult(handoverResult.analysis_result);
      } catch (error) {
        console.error('이관 분석 실패:', error);
      } finally {
        setIsAnalyzing(false);
      }
    } catch (error: any) {
      console.error('세션 수락 실패:', error);
      alert(error.message || '세션 수락에 실패했습니다.');
    } finally {
      setIsAccepting(false);
    }
  };

  // 마이크 버튼 클릭 핸들러
  const handleMicClick = async () => {
    if (isRecording) {
      // 녹음 중지 및 STT 처리
      const audioBlob = await stopRecording();

      if (!audioBlob) {
        console.error('녹음 데이터 없음');
        return;
      }

      setIsTranscribing(true);

      try {
        // STT 변환
        const sttResult = await transcribeAudio(audioBlob);
        const transcribedText = sttResult.transcribed_text;

        if (!transcribedText.trim()) {
          alert('음성을 인식할 수 없습니다. 다시 시도해주세요.');
          return;
        }

        // 변환된 텍스트를 입력창에 설정
        setInputValue(transcribedText);

      } catch (error) {
        console.error('STT 변환 실패:', error);
        alert('음성 변환에 실패했습니다. 다시 시도해주세요.');
      } finally {
        setIsTranscribing(false);
      }
    } else {
      // 녹음 시작
      await startRecording();
    }
  };

  return (
    <Container>
      {/* 대시보드 헤더 */}
      <DashboardHeader>
        <DashboardTitle>미래카드 AICC 상담 대시보드</DashboardTitle>
        <DashboardSubtitle>음성 AI 기반 고객 상담 서비스</DashboardSubtitle>
      </DashboardHeader>

      {/* 세션 선택 영역 */}
      <SessionSelectArea>
        <SessionSelectLabel>대기 세션:</SessionSelectLabel>
        <SessionSelect
          value={selectedSession?.session_id || ''}
          onChange={(e) => {
            const session = handoverSessions.find(s => s.session_id === e.target.value);
            if (session) handleSelectSession(session);
          }}
        >
          <option value="">-- 세션 선택 --</option>
          {handoverSessions.map(session => (
            <option key={session.session_id} value={session.session_id}>
              {session.session_id} {session.collected_info?._category ? `(${session.collected_info._category})` : ''}
            </option>
          ))}
        </SessionSelect>
        <RefreshButton
          onClick={() => fetchHandoverSessions(true)}
          $isLoading={isRefreshing}
          disabled={isRefreshing}
        >
          {isRefreshing ? '조회 중...' : '새로고침'}
        </RefreshButton>
        {selectedSession && !isSessionAccepted && !isSessionClosed && (
          <AcceptSessionButton
            onClick={handleAcceptSession}
            disabled={isAccepting}
          >
            {isAccepting ? '수락 중...' : '상담 수락'}
          </AcceptSessionButton>
        )}
        {isSessionAccepted && (
          <span style={{ color: '#4CAF50', fontWeight: 500, marginLeft: 12 }}>✓ 수락됨</span>
        )}
        {/* 세션 수량 표시 */}
        <SessionCountArea>
          <SessionCountItem>
            <SessionCountLabel>대기:</SessionCountLabel>
            <SessionCountValue $isAlert={handoverSessions.length - (isSessionAccepted && !isSessionClosed ? 1 : 0) > 0}>
              {handoverSessions.length - (isSessionAccepted && !isSessionClosed ? 1 : 0)}
            </SessionCountValue>
          </SessionCountItem>
          <SessionCountItem>
            <SessionCountLabel>상담 중:</SessionCountLabel>
            <SessionCountValue style={{ color: isSessionAccepted && !isSessionClosed ? '#4CAF50' : '#333' }}>
              {isSessionAccepted && !isSessionClosed ? 1 : 0}
            </SessionCountValue>
          </SessionCountItem>
          <SessionCountItem>
            <SessionCountLabel>완료:</SessionCountLabel>
            <SessionCountValue>{closedSessions.length}</SessionCountValue>
          </SessionCountItem>
        </SessionCountArea>
        {handoverSessions.length === 0 && (
          <NoSessionText>현재 연결 대기 중인 고객이 없습니다</NoSessionText>
        )}
        <SidebarToggleButton onClick={handleOpenSidebar}>
          상담 기록
        </SidebarToggleButton>
      </SessionSelectArea>

      {/* 상단: 상담 연결 상태 + Slot Filling + 시간 정보 */}
      <TopSection>
        {/* 왼쪽: 상담 연결 상태 */}
        <ConnectionStatusArea>
          <ConnectionTitle>{isSessionClosed ? '상담 종료' : '상담 연결'}</ConnectionTitle>
          <StatusIndicator $isConnected={selectedSession !== null} $isClosed={isSessionClosed} />
        </ConnectionStatusArea>

        {/* 중앙: Slot Filling 정보 */}
        <SlotFillingArea>
          <SlotItem>
            <SlotLabel>문의유형:</SlotLabel>
            <SlotValue>{selectedSession?.collected_info?._domain_name || selectedSession?.collected_info?.inquiry_type || '-'}</SlotValue>
          </SlotItem>
          <SlotItem>
            <SlotLabel>상세요청:</SlotLabel>
            <SlotValue>{selectedSession?.collected_info?._category || selectedSession?.collected_info?.inquiry_detail || '-'}</SlotValue>
          </SlotItem>
          {/* 동적 슬롯 표시 - 내부 필드(_로 시작)와 기본 필드 제외 */}
          {selectedSession?.collected_info && Object.entries(selectedSession.collected_info)
            .filter(([key, value]) => !key.startsWith('_') && !['inquiry_type', 'inquiry_detail', 'customer_name'].includes(key) && value !== null)
            .map(([key, value]) => (
              <SlotItem key={key}>
                <SlotLabel>{getSlotLabel(key)}:</SlotLabel>
                <SlotValue>{String(value) || '-'}</SlotValue>
              </SlotItem>
            ))
          }
        </SlotFillingArea>

        {/* 오른쪽: 시간 정보 */}
        <TimeInfoArea>
          <TimeItem>
            <TimeLabel>시작 시간:</TimeLabel>
            <TimeValue>{formatTime(startTime)}</TimeValue>
          </TimeItem>
          <TimeItem>
            <TimeLabel>종료 시간:</TimeLabel>
            <TimeValue>{formatTime(endTime)}</TimeValue>
          </TimeItem>
          <TimeItem>
            <TimeLabel>통화 시간:</TimeLabel>
            <TimeValue>{calculateDuration()}</TimeValue>
          </TimeItem>
        </TimeInfoArea>
      </TopSection>

      {/* 메인 컨텐츠 */}
      <MainContent>
        {/* 고객 대화창 */}
        <Section>
          <SectionHeader>
            고객 대화창
            {selectedSession && <LiveBadge>LIVE</LiveBadge>}
          </SectionHeader>
          <SectionBody>
            <ChatArea>
              {!selectedSession ? (
                <LoadingText>
                  왼쪽 상단에서 이관 대기 고객을 선택하세요.
                </LoadingText>
              ) : messages.length === 0 ? (
                <LoadingText>대화 내역을 불러오는 중...</LoadingText>
              ) : (
                messages.map(msg => (
                  <ChatMessage
                    key={msg.id}
                    align={msg.speaker === 'customer' ? 'right' : msg.speaker === 'system' ? 'center' : 'left'}
                  >
                    {msg.speaker !== 'system' && (
                      <MessageLabel type={msg.speaker} $isAi={msg.isAiGenerated}>
                        {msg.speaker === 'customer' ? '고객' : (msg.isAiGenerated ? 'AI 상담' : '상담사')}
                      </MessageLabel>
                    )}
                    <MessageBubble type={msg.speaker} $isAi={msg.isAiGenerated}>
                      {msg.message}
                    </MessageBubble>
                    <MessageTime>{msg.timestamp}</MessageTime>
                  </ChatMessage>
                ))
              )}
              {isSending && (
                <ChatMessage align="left">
                  <MessageLabel type="agent">상담사</MessageLabel>
                  <MessageBubble type="agent">전송 중...</MessageBubble>
                </ChatMessage>
              )}
              <div ref={chatEndRef} />
            </ChatArea>
          </SectionBody>
          <InputArea>
            <ChatInput
              type="text"
              placeholder={
                isSessionClosed
                  ? "상담이 종료되었습니다"
                  : selectedSession
                    ? "고객에게 보낼 메시지를 입력하세요..."
                    : "먼저 고객을 선택하세요"
              }
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={isSending || !selectedSession || isSessionClosed}
            />
            <SendButton
              onClick={handleSendMessage}
              disabled={isSending || !selectedSession || !inputValue.trim() || isSessionClosed}
            >
              전송
            </SendButton>
            <CloseSessionButton
              onClick={handleCloseSession}
              disabled={!selectedSession || isSessionClosed}
            >
              {isSessionClosed ? '종료됨' : '상담 종료'}
            </CloseSessionButton>
          </InputArea>
        </Section>

        {/* 상담 요약 및 수집 정보 */}
        <Section>
          <SectionHeader>상담 요약 및 수집 정보</SectionHeader>
          <SectionBody>
            {!selectedSession ? (
              <LoadingText>
                고객을 선택하면 AI 분석 결과가 표시됩니다.
              </LoadingText>
            ) : isAnalyzing ? (
              <LoadingText>AI가 대화를 분석 중입니다...</LoadingText>
            ) : analysisResult ? (
              <>
                <SummaryBlock>
                  <SummaryTitle>
                    고객 감정 분석
                    <SentimentBadge $sentiment={analysisResult.customer_sentiment} style={{ marginLeft: '10px' }}>
                      {getSentimentText(analysisResult.customer_sentiment)}
                    </SentimentBadge>
                  </SummaryTitle>
                </SummaryBlock>

                <SummaryBlock>
                  <SummaryTitle>AI 요약</SummaryTitle>
                  <SummaryText>{analysisResult.summary}</SummaryText>
                </SummaryBlock>

                <SummaryBlock>
                  <SummaryTitle>핵심 키워드</SummaryTitle>
                  <KeywordList>
                    {analysisResult.extracted_keywords.map((keyword, index) => (
                      <Keyword key={index}>{keyword}</Keyword>
                    ))}
                  </KeywordList>
                </SummaryBlock>

                {analysisResult.kms_recommendations.length > 0 && (
                  <SummaryBlock>
                    <SummaryTitle>추천 문서</SummaryTitle>
                    <InfoGrid>
                      {analysisResult.kms_recommendations.map((doc, index) => (
                        <InfoBox key={index}>
                          <InfoBoxValue>{doc}</InfoBoxValue>
                        </InfoBox>
                      ))}
                    </InfoGrid>
                  </SummaryBlock>
                )}
              </>
            ) : (
              <LoadingText>
                분석 결과가 없습니다.
              </LoadingText>
            )}
          </SectionBody>
        </Section>
      </MainContent>

      {/* 사이드바: 종료된 상담 기록 */}
      <SidebarOverlay $isOpen={isSidebarOpen} onClick={handleCloseSidebar} />
      <Sidebar $isOpen={isSidebarOpen}>
        <SidebarHeader>
          상담 기록
          <SidebarCloseButton onClick={handleCloseSidebar}>×</SidebarCloseButton>
        </SidebarHeader>
        <SidebarContent>
          {closedSessions.length === 0 ? (
            <LoadingText>종료된 상담이 없습니다.</LoadingText>
          ) : (
            closedSessions.map(session => (
              <ClosedSessionItem
                key={session.session_id}
                isSelected={selectedClosedSession?.session_id === session.session_id}
                onClick={() => handleSelectClosedSession(session)}
              >
                <ClosedSessionDate>
                  {new Date(session.updated_at).toLocaleString('ko-KR')}
                </ClosedSessionDate>
                <ClosedSessionName>
                  {session.collected_info?._category || session.collected_info?.inquiry_detail || '(상세 없음)'}
                </ClosedSessionName>
                <ClosedSessionType>
                  {session.collected_info?.inquiry_type || '(유형 없음)'}
                </ClosedSessionType>
              </ClosedSessionItem>
            ))
          )}

          {/* 선택된 세션의 대화 내용 */}
          {selectedClosedSession && historyMessages.length > 0 && (
            <HistoryChatArea>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>대화 내용</div>
              {historyMessages.map(msg => (
                <HistoryMessage key={msg.id} isUser={msg.role === 'user'}>
                  <HistoryBubble isUser={msg.role === 'user'}>
                    {msg.message}
                  </HistoryBubble>
                  <HistoryTime>
                    {new Date(msg.created_at).toLocaleTimeString('ko-KR', {
                      hour: '2-digit',
                      minute: '2-digit',
                      hour12: false
                    })}
                  </HistoryTime>
                </HistoryMessage>
              ))}
            </HistoryChatArea>
          )}
        </SidebarContent>
      </Sidebar>
    </Container>
  );
};

export default Dashboard;
