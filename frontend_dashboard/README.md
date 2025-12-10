# Agent Dashboard (상담원 대시보드)

Bank AICC 프로젝트의 상담원 대시보드 프론트엔드입니다.

## 실행 방법

### 1. 의존성 설치
```bash
cd agent-dashboard
npm install
```

### 2. 개발 서버 실행
```bash
npm start
```
[http://localhost:3001](http://localhost:3001)에서 확인할 수 있습니다.

### 3. 백엔드 서버
백엔드 서버가 `http://localhost:8000`에서 실행 중이어야 합니다.

## 주요 기능

- 실시간 고객-챗봇 대화 모니터링
- AI 분석 요약 (의도 분류, 감정 분석, 핵심 키워드)
- 세션 정보 확인
- 이관된 상담 세션 관리

## 기술 스택

- React 18 + TypeScript
- styled-components
- Axios

## 폴더 구조

```
src/
├── components/
│   ├── dashboard/    # 대시보드 컴포넌트
│   └── layout/       # 레이아웃 컴포넌트
├── pages/            # 페이지 컴포넌트
├── services/         # API 서비스
└── styles/           # 전역 스타일
```
