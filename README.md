# Tem_fa06-fin-aicc
- 삼정 Future Academy 06기 최종 프로젝트 템플릿입니다.
---------------------------------------

# 프로젝트 계획서

## 1. 프로젝트 개요
- **프로젝트명** : 심리스한 상담 경험을 제공하는 AI 상담 서비스 기획 프로젝트입니다.
- **목표** : 상담 맥락 단절을 해결하는 End-to-End AI 상담 에이전트
- **기간** : 2025년 10월 - 2025년 12월
- **팀명** : Linker

## 2. 프로젝트 일정
- **분석 및 설계** : 2025년 10월 - 11월
- **개발** : 2025년 11월 - 12월
- **테스트** : 2025년 12월 - 12월

## 3. 팀 구성
- **프로젝트 매니저** : A
- **AI/백엔드 모델** : B, C
- **Product 개발** : D
   
---------------------------------------

# 요구사항 정의서

## 1. 기능 요구사항
- [ ] 콜봇/챗봇 API 제공: `/api/v1/chat/message`
- [ ] 상담원 핸드오버 분석 API 제공: `/api/v1/handover/analyze`
- [ ] 음성 STT/TTS 모듈 제공: OpenAI Whisper, VITO STT, Hume/Humelo TTS, Google TTS
- [ ] 실시간(WebSocket) 음성 스트리밍 지원: Whisper/VITO STT, Hume/Humelo TTS
- [ ] Voice Conversion 데모 제공: Zonos 샘플 실행

## 2. 비기능 요구사항
- [ ] FastAPI 기반 REST 설계, Swagger 제공으로 확인 용이
- [ ] 확장성: 음성/LLM 엔진 교체 및 추가 연동 용이
- [ ] 보안: API 키 환경변수 관리, 최소 권한 원칙
----------------------------------------

# WBS
## 1. 기획
1.1. 문제 정의  
1.2. 요구사항 수집 및 우선순위 정의  
1.3. 인프라/보안 정책 수립  
1.4. 프로젝트 일정 확정 및 커뮤니케이션 플랜

## 2. 데이터 수집, 전처리
2.1. 은행 FAQ/상품 문서 조사  
2.2. KMS/검색 연동 설계 및 구축  
2.3. 음성 데이터 정리 및 전처리  
2.4. 프롬프트/시나리오 설계

## 3. 대화/분석 모델링
3.1. 의도 분류 및 정책 설계  
3.2. 챗봇 답변 템플릿/프롬프트 작성  
3.3. 감정 분석·키워드 추출 룰/모델 정의  
3.4. LLM/KMS 호출 흐름 설계

## 4. 서비스 개발
4.1. 백엔드 API(FastAPI) 구현  
4.2. 음성 파이프라인(STT/TTS) 모듈 구현 및 WebSocket 스트리밍  
4.3. 핸드오버 분석/요약 기능 구현  
4.4. 프런트엔드(AICC 콘솔/데모 UI) 연동

## 5. 테스트/고도화
5.1. 기능·부하 테스트  
5.2. UX 개선 및 오류 처리 고도화  
5.3. 보안/로그/모니터링 정비  
5.4. QA 및 사용자 피드백 반영

## 6. 결과 산출 및 보고
6.1. 결과 정리/슬라이드 작성  
6.2. 보고서/데모 영상 제작  
6.3. 최종 발표

-----------------------------------------

# 모델 정의서

## 1. 데이터 모델 (예시)
- **사용자 테이블**
  - `user_id` (PK), `username`, `password`, `email`, `role`
- **분석 결과 테이블**
  - `result_id` (PK), `user_id` (FK), `result_data` (JSON)

## 2. 객체/엔진
- **챗봇/콜봇 엔진** : `app/api/v1/chat.py` (목 응답 → LLM/KMS 연동 예정)
- **핸드오버 분석 엔진** : `app/api/v1/handover.py` (감정/요약/키워드/KMS 추천)
- **음성 엔진** :
  - `app/services/voice` : OpenAI Whisper STT, OpenAI TTS
  - `app/services/voice2` : VITO STT(diarization)
  - `app/services/websocket` : Whisper/VITO STT, Hume/Humelo TTS WebSocket/HTTP
  - `app/services/Zonos` : Voice Conversion 데모

----------------------------------------

# 최종 보고서 (요약)

## 1. 프로젝트 개요
- **목표**: 콜봇/챗봇, 핸드오버, 음성 파이프라인이 통합된 AICC 백엔드 데모 구축
- **기간**: 2025년 10월 - 2025년 12월

## 2. 주요 성과
- 대화·핸드오버 API 스켈레톤 제공 및 Swagger 문서화
- Whisper/VITO/Hume/Humelo/Google TTS 등 음성 모듈 연동 샘플 제공
- WebSocket 기반 실시간 STT/TTS 파이프라인 예제 제공
- Voice Conversion(Zonos) 데모 환경 제공

## 3. 향후 개선 과제
- 목 응답을 실데이터 기반 LLM/KMS 연동으로 대체
- 상담원 콘솔/프런트엔드와 인증·권한 통합
- 모니터링/로깅/데이터 거버넌스 강화

-----------------------------------------

# 참고
- API 문서: `http://localhost:8000/docs`
- 실행: `uvicorn app.main:app --reload --port 8000`
- 환경 변수: `OPENAI_API_KEY`, `VITO_CLIENT_ID`, `VITO_CLIENT_SECRET`, `HUME_API_KEY`, `HUME_VOICE_ID`, `HUME_TTS_HTTP_URL`, `GOOGLE_APPLICATION_CREDENTIALS`
