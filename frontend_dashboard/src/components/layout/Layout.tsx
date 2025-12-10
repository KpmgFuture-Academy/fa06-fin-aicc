import React, { useState } from 'react';
import styled from 'styled-components';
import Header from './Header';
import Sidebar from './Sidebar';

const LayoutContainer = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
`;

const MainWrapper = styled.div`
  display: flex;
  flex: 1;
  overflow: hidden;
`;

const SidebarWrapper = styled.div<{ isOpen: boolean }>`
  width: ${props => props.isOpen ? '240px' : '0'};
  overflow: hidden;
  transition: width 0.3s ease;
`;

const MainContent = styled.main`
  flex: 1;
  overflow-y: auto;
  padding: 20px;
`;

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);

  const handleToggleSidebar = () => {
    setSidebarOpen(prev => !prev);
  };

  return (
    <LayoutContainer>
      <Header sidebarOpen={sidebarOpen} onToggleSidebar={handleToggleSidebar} />
      <MainWrapper>
        <SidebarWrapper isOpen={sidebarOpen}>
          <Sidebar />
        </SidebarWrapper>
        <MainContent>
          {children}
        </MainContent>
      </MainWrapper>
    </LayoutContainer>
  );
};

export default Layout;
