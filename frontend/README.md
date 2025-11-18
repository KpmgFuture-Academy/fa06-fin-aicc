# Bank AICC Frontend

AI 상담 챗봇 프론트엔드 애플리케이션

## 기술 스택

- React 18
- TypeScript
- Vite
- Axios

## 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 빌드
npm run build

# 빌드 결과 미리보기
npm run preview
```

## 환경 변수

`.env` 파일을 생성하여 API 서버 주소를 설정할 수 있습니다:

```
VITE_API_BASE_URL=http://localhost:8000
```

## 주요 기능

- 실시간 채팅 인터페이스
- LangGraph 워크플로우와 연동
- 세션 관리
- 상담원 이관 요청
- 대화 이력 표시

