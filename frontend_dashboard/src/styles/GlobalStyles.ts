import { createGlobalStyle } from 'styled-components';

// 하나카드 컬러 테마
export const theme = {
  colors: {
    primary: '#00857C',      // 하나 민트
    primaryDark: '#006B63',
    secondary: '#1A1A1A',    // 다크
    background: '#F5F5F5',
    white: '#FFFFFF',
    alert: '#E53935',        // 경고
    warning: '#FF9800',
    success: '#4CAF50',
    text: '#333333',
    textLight: '#666666',
    border: '#E0E0E0',
  },
  shadows: {
    card: '0 2px 8px rgba(0, 0, 0, 0.1)',
    header: '0 2px 4px rgba(0, 0, 0, 0.08)',
  }
};

export const GlobalStyles = createGlobalStyle`
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  body {
    font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: ${theme.colors.background};
    color: ${theme.colors.text};
    line-height: 1.5;
  }

  button {
    cursor: pointer;
    border: none;
    outline: none;
  }

  a {
    text-decoration: none;
    color: inherit;
  }
`;
