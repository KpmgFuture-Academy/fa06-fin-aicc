import React from 'react';
import styled from 'styled-components';
import { theme } from '../../styles/GlobalStyles';
import { navigationMenu, waitingConsultations } from '../../data/dummyData';

const SidebarContainer = styled.aside`
  width: 240px;
  background-color: ${theme.colors.white};
  border-right: 1px solid ${theme.colors.border};
  display: flex;
  flex-direction: column;
  height: 100%;
`;

const SectionTitle = styled.h3`
  font-size: 12px;
  font-weight: 600;
  color: ${theme.colors.textLight};
  text-transform: uppercase;
  padding: 16px 16px 8px;
  letter-spacing: 0.5px;
`;

const MenuList = styled.ul`
  list-style: none;
  padding: 0 8px;
`;

const MenuItem = styled.li<{ active?: boolean; urgent?: boolean }>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  background-color: ${props => props.active ? theme.colors.primary + '10' : 'transparent'};
  border-left: 3px solid ${props => props.active ? theme.colors.primary : 'transparent'};
  transition: all 0.2s ease;

  &:hover {
    background-color: ${theme.colors.primary}10;
  }

  ${props => props.urgent && `
    animation: pulse 2s infinite;
    @keyframes pulse {
      0%, 100% { background-color: transparent; }
      50% { background-color: ${theme.colors.alert}15; }
    }
  `}
`;

const MenuItemLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const MenuIcon = styled.span`
  font-size: 18px;
`;

const MenuLabel = styled.span<{ active?: boolean }>`
  font-size: 14px;
  font-weight: ${props => props.active ? 600 : 400};
  color: ${props => props.active ? theme.colors.primary : theme.colors.text};
`;

const MenuCount = styled.span<{ urgent?: boolean }>`
  background-color: ${props => props.urgent ? theme.colors.alert : theme.colors.background};
  color: ${props => props.urgent ? theme.colors.white : theme.colors.textLight};
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  min-width: 24px;
  text-align: center;
`;

const Divider = styled.hr`
  border: none;
  border-top: 1px solid ${theme.colors.border};
  margin: 16px 0;
`;

const WaitingList = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
`;

const WaitingItem = styled.div<{ priority: string }>`
  display: flex;
  flex-direction: column;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background-color: ${theme.colors.background};
  border-left: 3px solid ${props => {
    switch (props.priority) {
      case 'urgent': return theme.colors.alert;
      case 'high': return theme.colors.warning;
      default: return theme.colors.primary;
    }
  }};
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: ${theme.shadows.card};
  }
`;

const WaitingHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
`;

const WaitingName = styled.span`
  font-size: 14px;
  font-weight: 600;
  color: ${theme.colors.secondary};
`;

const WaitingTime = styled.span<{ urgent?: boolean }>`
  font-size: 12px;
  font-weight: 500;
  color: ${props => props.urgent ? theme.colors.alert : theme.colors.textLight};
`;

const WaitingCategory = styled.span`
  font-size: 12px;
  color: ${theme.colors.textLight};
`;

const Sidebar: React.FC = () => {
  const [activeMenu, setActiveMenu] = React.useState('limit');

  return (
    <SidebarContainer>
      <SectionTitle>업무 유형</SectionTitle>
      <MenuList>
        {navigationMenu.map(item => (
          <MenuItem
            key={item.id}
            active={activeMenu === item.id}
            urgent={item.urgent}
            onClick={() => setActiveMenu(item.id)}
          >
            <MenuItemLeft>
              <MenuIcon>{item.icon}</MenuIcon>
              <MenuLabel active={activeMenu === item.id}>{item.label}</MenuLabel>
            </MenuItemLeft>
            <MenuCount urgent={item.urgent}>{item.count}</MenuCount>
          </MenuItem>
        ))}
      </MenuList>

      <Divider />

      <SectionTitle>대기 중인 상담</SectionTitle>
      <WaitingList>
        {waitingConsultations.map(item => (
          <WaitingItem key={item.id} priority={item.priority}>
            <WaitingHeader>
              <WaitingName>{item.customerName}</WaitingName>
              <WaitingTime urgent={item.priority === 'urgent'}>
                {item.waitTime}
              </WaitingTime>
            </WaitingHeader>
            <WaitingCategory>{item.category}</WaitingCategory>
          </WaitingItem>
        ))}
      </WaitingList>
    </SidebarContainer>
  );
};

export default Sidebar;
