import React from 'react';
import styled from 'styled-components';
import { theme } from '../../styles/GlobalStyles';
import { agentInfo, queueInfo, currentCustomer } from '../../data/dummyData';

const HeaderContainer = styled.header`
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: ${theme.colors.white};
  padding: 12px 24px;
  box-shadow: ${theme.shadows.header};
  border-bottom: 2px solid ${theme.colors.primary};
`;

const LeftSection = styled.div`
  display: flex;
  align-items: center;
  gap: 24px;
`;

const RightSection = styled.div`
  display: flex;
  align-items: center;
  gap: 24px;
`;

const Logo = styled.div`
  font-size: 20px;
  font-weight: 700;
  color: ${theme.colors.primary};
`;

const StatusToggle = styled.div<{ status: string }>`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 20px;
  background-color: ${props => {
    switch (props.status) {
      case 'available': return '#E8F5E9';
      case 'busy': return '#FFEBEE';
      case 'break': return '#FFF3E0';
      default: return '#EEEEEE';
    }
  }};
  cursor: pointer;
`;

const StatusDot = styled.span<{ status: string }>`
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: ${props => {
    switch (props.status) {
      case 'available': return theme.colors.success;
      case 'busy': return theme.colors.alert;
      case 'break': return theme.colors.warning;
      default: return '#9E9E9E';
    }
  }};
`;

const StatusText = styled.span`
  font-size: 14px;
  font-weight: 500;
`;

const StatBox = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 16px;
  border-right: 1px solid ${theme.colors.border};

  &:last-child {
    border-right: none;
  }
`;

const StatLabel = styled.span`
  font-size: 11px;
  color: ${theme.colors.textLight};
`;

const StatValue = styled.span<{ warning?: boolean }>`
  font-size: 18px;
  font-weight: 700;
  color: ${props => props.warning ? theme.colors.alert : theme.colors.secondary};
`;

const CustomerInfo = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background-color: ${theme.colors.background};
  border-radius: 8px;
`;

const CustomerDetail = styled.div`
  display: flex;
  flex-direction: column;
`;

const CustomerName = styled.span`
  font-size: 14px;
  font-weight: 600;
  color: ${theme.colors.secondary};
`;

const CustomerMeta = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
`;

const Badge = styled.span<{ type: 'vip' | 'privacy' | 'sla' }>`
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  background-color: ${props => {
    switch (props.type) {
      case 'vip': return '#FFD700';
      case 'privacy': return theme.colors.success;
      case 'sla': return theme.colors.alert;
    }
  }};
  color: ${props => props.type === 'vip' ? '#333' : '#fff'};
`;

const SidebarToggleButton = styled.button<{ isOpen: boolean }>`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background-color: ${props => props.isOpen ? theme.colors.primary : theme.colors.background};
  color: ${props => props.isOpen ? theme.colors.white : theme.colors.text};
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;

  &:hover {
    background-color: ${props => props.isOpen ? theme.colors.primaryDark : theme.colors.border};
  }
`;

const ToggleIcon = styled.span<{ isOpen: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: ${props => props.isOpen ? 'rotate(0deg)' : 'rotate(180deg)'};
`;

const getStatusText = (status: string) => {
  switch (status) {
    case 'available': return '상담 가능';
    case 'busy': return '상담 중';
    case 'break': return '휴식';
    default: return '오프라인';
  }
};

interface HeaderProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

const Header: React.FC<HeaderProps> = ({ sidebarOpen, onToggleSidebar }) => {
  return (
    <HeaderContainer>
      <LeftSection>
        <Logo>상담 대시보드</Logo>

        <StatusToggle status={agentInfo.status}>
          <StatusDot status={agentInfo.status} />
          <StatusText>{getStatusText(agentInfo.status)}</StatusText>
        </StatusToggle>

        <StatBox>
          <StatLabel>오늘 콜</StatLabel>
          <StatValue>{agentInfo.todayCalls}</StatValue>
        </StatBox>

        <StatBox>
          <StatLabel>대기열</StatLabel>
          <StatValue warning={queueInfo.waiting > 2}>{queueInfo.waiting}</StatValue>
        </StatBox>

        <StatBox>
          <StatLabel>평균 대기</StatLabel>
          <StatValue>{queueInfo.avgWaitTime}</StatValue>
        </StatBox>

        {queueInfo.slaWarning && (
          <Badge type="sla">SLA {queueInfo.slaPercentage}%</Badge>
        )}
      </LeftSection>

      <RightSection>
        <CustomerInfo>
          <CustomerDetail>
            <CustomerName>
              {currentCustomer.name}
              <Badge type="vip" style={{ marginLeft: 8 }}>{currentCustomer.memberGrade}</Badge>
            </CustomerName>
            <CustomerMeta>
              {currentCustomer.customerId} | {currentCustomer.phone}
            </CustomerMeta>
          </CustomerDetail>
          {currentCustomer.isPrivacyAgreed && (
            <Badge type="privacy">개인정보 동의</Badge>
          )}
        </CustomerInfo>

        <StatBox>
          <StatLabel>만족도</StatLabel>
          <StatValue>{agentInfo.satisfaction}</StatValue>
        </StatBox>

        <SidebarToggleButton isOpen={sidebarOpen} onClick={onToggleSidebar}>
          <ToggleIcon isOpen={sidebarOpen}>◀</ToggleIcon>
          {sidebarOpen ? '메뉴 숨기기' : '메뉴 보기'}
        </SidebarToggleButton>
      </RightSection>
    </HeaderContainer>
  );
};

export default Header;
