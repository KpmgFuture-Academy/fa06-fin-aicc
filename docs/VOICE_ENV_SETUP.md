# 음성 서비스(STT/TTS) 환경 설정 가이드

## 개요
- **STT (음성→텍스트)**: VITO (Return Zero)
- **TTS (텍스트→음성)**: OpenAI TTS-1

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

## 2. OpenAI TTS 설정

### 2-1. API 키
기존 `OPENAI_API_KEY`를 그대로 사용합니다.

### 2-2. 음성 종류 선택
`.env` 파일에 추가:
```env
# 음성 옵션: alloy, echo, fable, onyx, nova, shimmer
TTS_VOICE=alloy
```

| 음성 | 특징 | 추천 용도 |
|------|------|----------|
| `alloy` | 중성적, 균형 잡힌 | 일반 상담 (기본값) |
| `echo` | 따뜻하고 자연스러운 | 친근한 안내 |
| `fable` | 표현력 있는 | 스토리텔링 |
| `onyx` | 깊고 권위 있는 남성 | 공식적 안내 |
| `nova` | 친근하고 밝은 여성 | 환영 메시지 |
| `shimmer` | 차분하고 부드러운 | 금융 상담 |

### 2-3. 모델 선택
```env
# tts-1: 빠른 응답, 일반 품질 (권장)
# tts-1-hd: 느린 응답, 고품질
TTS_MODEL=tts-1
```

| 모델 | 응답 속도 | 품질 | 비용 |
|------|----------|------|------|
| `tts-1` | 빠름 (~1초) | 일반 | $0.015/1K chars |
| `tts-1-hd` | 느림 (~2초) | 고품질 | $0.030/1K chars |

---

## 3. 전체 .env 예시

```env
# ========== 기존 설정 ==========
OPENAI_API_KEY=sk-your-openai-api-key
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aicc_db?charset=utf8mb4

# ========== STT 설정 (VITO) ==========
VITO_CLIENT_ID=your-vito-client-id
VITO_CLIENT_SECRET=your-vito-client-secret

# ========== TTS 설정 (OpenAI) ==========
TTS_VOICE=alloy
TTS_MODEL=tts-1
```

---

## 4. 설정 확인

서버 시작 시 로그에서 확인:
```
✅ VITO STT 설정 확인 완료
✅ OpenAI TTS 설정 확인 완료 (voice: alloy, model: tts-1)
```

---

## 5. 문제 해결

### VITO 인증 실패
```
VitoSTTError: VITO auth failed
```
- `VITO_CLIENT_ID`와 `VITO_CLIENT_SECRET` 확인
- [VITO 콘솔](https://console.vito.ai/)에서 애플리케이션 상태 확인

### TTS 요청 실패
```
TTSError: OpenAI TTS request failed
```
- `OPENAI_API_KEY` 유효성 확인
- API 사용량 한도 확인
- 텍스트 길이 제한 (4096자) 확인

### 토큰 만료 (VITO)
- VITO 토큰은 6시간 유효
- 서비스에서 자동 갱신 처리됨

