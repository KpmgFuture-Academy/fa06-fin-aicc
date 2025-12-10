# CHANGELOG

이 파일은 `feature/ai_engine_2nd` 브랜치의 변경 사항을 기록합니다.

---

## [Unreleased] - 2025-12-10

### Added
- **세션 ID 포맷 개선** (`voice-chatbot-revision/src/services/api.ts`) - 2025-12-10
  - 기존 `sess_timestamp_random` 형식에서 `YYYYMMDD_HHmm_XXX` 형식으로 변경
  - `generateSessionId()` 함수 추가: 날짜_시간_순번 형식 생성
  - `formatSessionIdForDisplay()` 함수 추가: 세션 ID를 `MM-DD HH:mm #XXX` 형식으로 표시
  - 일별 세션 순번 관리 (localStorage 기반)

### Changed
- **TTS 엔드포인트 에러 로깅 강화** (`app/api/v1/voice.py`) - 2025-12-10
  - `/voice/tts` 엔드포인트에 상세 로깅 추가
  - 요청 수신, 성공, TTSError, 예기치 않은 오류 각각에 대한 로그 추가

- **헤더 UI 개선** (`voice-chatbot-revision/src/App.tsx`, `App.css`) - 2025-12-10
  - 세션 ID를 헤더에 표시 (`formatSessionIdForDisplay` 함수 사용)
  - 헤더 내 세션 정보 스타일링 추가 (`.session-info-header`, `.session-id`)
  - 반응형 레이아웃 개선

### Fixed
- **텍스트 채팅 엔드포인트 경로 수정** (`voice-chatbot-revision/src/services/api.ts`) - 2025-12-10
  - `/api/v1/chat` → `/api/v1/chat/message`로 경로 수정
  - 404 Not Found 오류 해결

- **Google TTS API 키 환경변수 추가** (`.env`) - 2025-12-10
  - `GEM_API_KEY` 추가 (`google_tts/tts4.py`에서 사용)
  - Google Cloud Text-to-Speech API 활성화 필요

---

## [Previous] - 2025-12-09

### Added
- **입력 검증 레이어 (External Validation Layer)** (`app/services/workflow_service.py`) - 2025-12-09
  - LangGraph 워크플로우 진입 전 사용자 입력 검증 기능 추가
  - 빈 입력 검증: 2자 미만의 입력은 조기 반환
  - 매우 긴 입력 검증: 2000자 초과 입력은 조기 반환
  - 검증 실패 시 LangGraph 워크플로우를 실행하지 않고 즉시 응답 반환
  - 상세 문서: `docs/INPUT_VALIDATION_LAYER.md`

- **E2E 평가 파이프라인 STT/TTS 어댑터 추가** - 2025-12-09
  - STT 어댑터 (`e2e_evaluation_pipeline/adapters/stt_adapter.py`)
    - VITO STT 서비스 연동
    - WER(Word Error Rate), CER(Character Error Rate) 평가 메트릭 지원
  - TTS 어댑터 (`e2e_evaluation_pipeline/adapters/tts_adapter.py`)
    - Google TTS 서비스 연동
    - 합성 성능 및 레이턴시 평가 지원

- **Silero VAD 서비스 추가** (`app/services/voice/silero_vad_service.py`)
  - 딥러닝 기반 음성 활동 감지 (Voice Activity Detection)
  - 노이즈, 키보드 소리 등 비음성 필터링
  - 실시간 스트리밍 처리 지원

- **VAD 기반 실시간 스트리밍 엔드포인트** (`app/api/v1/voice_ws.py`)
  - `WS /api/v1/voice/streaming/{session_id}` - Silero VAD 기반 실시간 음성 스트리밍
  - `GET /api/v1/voice/vad/status` - VAD 서비스 상태 확인
  - `VoiceStreamSession` 클래스 - VAD 기반 세션 관리
  - 2초 침묵 후 자동 STT/AI/TTS 처리 (Barge-in 지원)

- **e2e_evaluation_pipeline** (stash에서 복원)
  - E2E 평가 파이프라인 전체 구조
  - STT, Intent, RAG, Slot Filling, Summary, Flow 메트릭
  - HTML/JSON 리포트 생성기

- **voice-chatbot-revision 프론트엔드 추가** (`voice-chatbot-revision/`)
  - `voice-chatbot-revision` 브랜치에서 가져옴
  - Silero VAD 기반 음성 입력 UI
  - `VoiceButton` 컴포넌트 - 마이크 녹음 버튼
  - `useVoiceStream` 훅 - 양방향 실시간 스트리밍 (STT + AI + TTS)
  - Barge-in 지원 (TTS 재생 중 음성 입력 시 중단)
  - 백엔드 `/api/v1/voice/streaming/{session_id}` 엔드포인트와 연동

### Changed
- **voice_ws.py 업데이트**
  - `silero_vad_service` import 추가
  - `pcm_to_wav` import 추가 (STT 서비스에서)
  - Google TTS (`tts_service_google.py`) 유지하면서 VAD 기능 병합

- **answer_agent.py 프롬프트 개선** (stash에서 복원)
  - 카드/금융 관련 상담 전용 응답 규칙 추가
  - Out-of-scope 질문 처리 로직 개선
  - 의미 없는 입력, 욕설, 외국어 처리 규칙 추가

- **vector_store.py L2 거리 계산 수정** (stash에서 복원)
  - L2 거리를 유사도 점수로 변환하는 공식 수정
  - `1/(1+distance)` 공식 적용 (기존: `1-distance`)

- **handover.py 엔드포인트 추가** (`app/api/v1/handover.py`)
  - `POST /api/v1/handover/request` 추가 (기존 `/analyze`와 동일 기능)
  - 프론트엔드(`voice-chatbot-revision`)와 API 경로 일치

- **voice-chatbot-revision 프론트엔드 Handover 스키마 수정**
  - `api.ts`: `HandoverResponse` 타입을 백엔드 스키마에 맞게 수정
  - `App.tsx`: Handover 모달 UI를 `analysis_result` 구조에 맞게 수정
  - 고객 감정, 요약, 핵심 키워드, 추천 문서 표시

### Stash 복원 내역
- `stash@{2}` (2025-12-09 13:04) - e2e_evaluation_pipeline, answer_agent, vector_store
- `stash@{3}` (2025-12-03 10:16) - state.py 수정

---

## 브랜치 정보

- **Development 브랜치**: `feature/ai_engine_2nd`
- **Base 브랜치**: `main`
- **최신 Pull**: 2025-12-09 (12개 커밋 반영)
  - Google TTS 추가
  - 데이터 변환 스크립트 추가
  - KB 하나카드 38개 카테고리 데이터 추가
