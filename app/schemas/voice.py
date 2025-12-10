"""음성 API 스키마

STT(음성→텍스트), TTS(텍스트→음성), 음성 채팅 관련 요청/응답 정의.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.common import IntentType, ActionType


# ========== STT 관련 ==========

class STTSegment(BaseModel):
    """음성 인식 세그먼트"""
    text: str
    start: Optional[float] = Field(None, description="시작 시간 (초)")
    end: Optional[float] = Field(None, description="종료 시간 (초)")
    confidence: Optional[float] = Field(None, description="신뢰도 (0~1)")
    speaker: Optional[str] = Field(None, description="화자 ID (diarization 사용 시)")


class STTResponse(BaseModel):
    """STT 전용 응답"""
    text: str = Field(..., description="인식된 텍스트")
    language: Optional[str] = Field(None, description="감지된 언어")
    segments: List[STTSegment] = Field(default_factory=list, description="세그먼트 목록")
    duration_ms: Optional[int] = Field(None, description="처리 시간 (밀리초)")


# ========== TTS 관련 ==========

class TTSRequest(BaseModel):
    """TTS 전용 요청"""
    text: str = Field(..., max_length=4096, description="변환할 텍스트 (최대 4096자)")
    voice: Optional[str] = Field(None, description="음성 종류 (None이면 서비스 기본값 사용)")
    format: str = Field("mp3", description="출력 포맷 (mp3, opus, aac, flac, wav)")


class TTSResponse(BaseModel):
    """TTS 전용 응답"""
    audio_base64: str = Field(..., description="Base64 인코딩된 음성 데이터")
    format: str = Field(..., description="음성 포맷")
    voice: Optional[str] = Field(None, description="사용된 음성")
    text_length: int = Field(..., description="입력 텍스트 길이")
    audio_size_bytes: int = Field(..., description="음성 데이터 크기 (바이트)")


# ========== 음성 채팅 (통합) ==========

class VoiceChatResponse(BaseModel):
    """음성 채팅 응답 (STT → 워크플로우 → TTS)"""
    
    # AI 응답
    ai_message: str = Field(..., description="AI 응답 텍스트")
    audio_base64: Optional[str] = Field(None, description="Base64 인코딩된 음성 응답")
    audio_format: str = Field("mp3", description="음성 포맷")
    
    # 워크플로우 결과
    intent: IntentType = Field(..., description="분류된 의도")
    suggested_action: ActionType = Field(..., description="권장 액션")
    
    # STT 결과
    transcribed_text: str = Field(..., description="STT로 인식된 고객 발화")
    
    # 메타데이터
    stt_duration_ms: Optional[int] = Field(None, description="STT 처리 시간")
    tts_duration_ms: Optional[int] = Field(None, description="TTS 처리 시간")
    total_duration_ms: Optional[int] = Field(None, description="전체 처리 시간")


# ========== 토큰 정보 (디버깅용) ==========

class TokenInfoResponse(BaseModel):
    """VITO 토큰 정보 응답"""
    has_token: bool = Field(..., description="토큰 존재 여부")
    is_valid: bool = Field(..., description="토큰 유효 여부")
    expiry_datetime: Optional[str] = Field(None, description="만료 일시")
    remaining_seconds: float = Field(..., description="남은 유효 시간 (초)")


# ========== WebSocket 메시지 타입 ==========

class WSMessageType:
    """WebSocket 메시지 타입 상수"""
    # 클라이언트 → 서버
    AUDIO_START = "audio_start"      # 음성 전송 시작
    AUDIO_CHUNK = "audio_chunk"      # 음성 데이터 청크
    AUDIO_END = "audio_end"          # 음성 전송 종료
    TEXT_MESSAGE = "text_message"    # 텍스트 메시지
    PING = "ping"                    # 연결 확인
    
    # 서버 → 클라이언트
    CONNECTED = "connected"          # 연결 완료
    STT_RESULT = "stt_result"        # STT 결과 (중간/최종)
    AI_RESPONSE = "ai_response"      # AI 응답 텍스트
    TTS_AUDIO = "tts_audio"          # TTS 음성 데이터
    ERROR = "error"                  # 에러
    PONG = "pong"                    # Ping 응답


class WSMessage(BaseModel):
    """WebSocket 메시지 기본 형식"""
    type: str = Field(..., description="메시지 타입")
    data: Optional[dict] = Field(None, description="메시지 데이터")
    timestamp: Optional[float] = Field(None, description="타임스탬프 (Unix)")


class WSAudioStartData(BaseModel):
    """음성 전송 시작 데이터"""
    language: str = Field("ko", description="언어 코드")
    tts_voice: Optional[str] = Field(None, description="TTS 음성 (None이면 서비스 기본값)")
    diarize: bool = Field(False, description="화자 분리 여부")


class WSSTTResultData(BaseModel):
    """STT 결과 데이터"""
    text: str = Field(..., description="인식된 텍스트")
    is_final: bool = Field(False, description="최종 결과 여부")
    confidence: Optional[float] = Field(None, description="신뢰도")


class WSAIResponseData(BaseModel):
    """AI 응답 데이터"""
    text: str = Field(..., description="AI 응답 텍스트")
    intent: str = Field(..., description="분류된 의도")
    suggested_action: str = Field(..., description="권장 액션")


class WSTTSAudioData(BaseModel):
    """TTS 음성 데이터"""
    audio_base64: str = Field(..., description="Base64 인코딩된 음성")
    format: str = Field("mp3", description="음성 포맷")
    is_final: bool = Field(True, description="마지막 청크 여부")

