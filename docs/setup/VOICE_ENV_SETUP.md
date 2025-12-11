# 음성 서비스(STT/TTS) 환경 설정 가이드

## 개요
- **STT (음성→텍스트)**: VITO (Return Zero)
- **TTS (텍스트→음성)**: Google Cloud Text-to-Speech

---

## 1. VITO STT 설정

### 1-1. API 키 발급
1. [VITO 개발자 포털](https://developers.vito.ai/) 접속
2. 회원가입 및 로그인
3. "애플리케이션 만들기" 클릭
4. `Client ID`와 `Client Secret` 복사

### 1-2. 요금제
| 플랜 | 무료 제공량 | 초과 요금 |
|------|------------|----------|
| 무료 | 월 300분 | - |
| 유료 | - | 분당 약 15원 |

### 1-3. 환경 변수 설정
`.env` 파일에 추가:
```env
VITO_CLIENT_ID=your-client-id-here
VITO_CLIENT_SECRET=your-client-secret-here
```

---

## 2. Google Cloud TTS 설정

### 2-1. Google Cloud 프로젝트 설정
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" > "라이브러리" 이동
4. "Cloud Text-to-Speech API" 검색 후 **사용 설정**

### 2-2. API 키 발급
1. "API 및 서비스" > "사용자 인증 정보" 이동
2. "사용자 인증 정보 만들기" > "API 키" 클릭
3. 생성된 API 키 복사
4. (선택) API 키 제한 설정:
   - "API 키 수정" 클릭
   - "API 제한사항" > "키 제한" 선택
   - "Cloud Text-to-Speech API" 선택

### 2-3. 환경 변수 설정
`.env` 파일에 추가:
```env
GOOGLE_TTS_API_KEY=your-google-tts-api-key-here
```

### 2-4. 요금제
| 유형 | 무료 제공량 | 초과 요금 |
|------|------------|----------|
| Standard | 월 400만 자 | $4/100만 자 |
| WaveNet | 월 100만 자 | $16/100만 자 |
| Neural2 | 월 100만 자 | $16/100만 자 |

### 2-5. 음성 옵션
현재 기본 설정: `ko-KR-Neural2-B` (한국어 남성 음성)

| 음성 ID | 성별 | 유형 | 특징 |
|---------|------|------|------|
| ko-KR-Neural2-A | 여성 | Neural2 | 자연스러운 여성 음성 |
| ko-KR-Neural2-B | 남성 | Neural2 | 자연스러운 남성 음성 |
| ko-KR-Neural2-C | 여성 | Neural2 | 또 다른 여성 음성 |
| ko-KR-Standard-A | 여성 | Standard | 기본 여성 음성 |
| ko-KR-Standard-B | 여성 | Standard | 기본 여성 음성 |
| ko-KR-Standard-C | 남성 | Standard | 기본 남성 음성 |
| ko-KR-Standard-D | 남성 | Standard | 기본 남성 음성 |
| ko-KR-Wavenet-A | 여성 | WaveNet | 고품질 여성 음성 |
| ko-KR-Wavenet-B | 여성 | WaveNet | 고품질 여성 음성 |
| ko-KR-Wavenet-C | 남성 | WaveNet | 고품질 남성 음성 |
| ko-KR-Wavenet-D | 남성 | WaveNet | 고품질 남성 음성 |

---

## 3. 전체 .env 예시

```env
# ========== 기존 설정 ==========
OPENAI_API_KEY=sk-your-openai-api-key
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aicc_db?charset=utf8mb4

# ========== STT 설정 (VITO) ==========
VITO_CLIENT_ID=your-vito-client-id
VITO_CLIENT_SECRET=your-vito-client-secret

# ========== TTS 설정 (Google Cloud) ==========
GOOGLE_TTS_API_KEY=your-google-tts-api-key
```

---

## 4. 설정 확인

서버 시작 시 로그에서 확인:
```
✅ VITO STT 설정 확인 완료
✅ Google TTS 설정 확인 완료 (voice: ko-KR-Neural2-B)
```

---

## 5. 문제 해결

### VITO 인증 실패
```
VitoSTTError: VITO auth failed
```
- `VITO_CLIENT_ID`와 `VITO_CLIENT_SECRET` 확인
- [VITO 콘솔](https://console.vito.ai/)에서 애플리케이션 상태 확인

### Google TTS 요청 실패 (500 에러)
```
TTSError: Google TTS API request failed
```
- `GOOGLE_TTS_API_KEY` 설정 확인
- Google Cloud Console에서 API 활성화 확인
- API 키 제한 설정 확인

### 토큰 만료 (VITO)
- VITO 토큰은 6시간 유효
- 서비스에서 자동 갱신 처리됨

---

## 6. 관련 코드 위치

| 파일 | 설명 |
|------|------|
| `app/services/voice/stt_service.py` | VITO STT 서비스 |
| `app/services/voice/tts_service_google.py` | Google TTS 서비스 |
| `app/api/v1/voice_ws.py` | WebSocket 음성 스트리밍 |
| `app/api/v1/voice.py` | REST API 음성 엔드포인트 |
