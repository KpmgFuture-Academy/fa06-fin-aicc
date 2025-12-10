"""음성 채팅 API - STT(VITO) + TTS(OpenAI)

엔드포인트:
- POST /api/v1/voice/message : 음성 채팅 (STT → 워크플로우 → TTS)
- POST /api/v1/voice/stt : STT 전용 (테스트/디버깅용)
- POST /api/v1/voice/tts : TTS 전용 (테스트/디버깅용)
- GET  /api/v1/voice/token-info : VITO 토큰 정보 (디버깅용)
"""

import base64
import logging
import time
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, status
from fastapi.responses import Response

from app.schemas.voice import (
    VoiceChatResponse,
    STTResponse,
    STTSegment,
    TTSRequest,
    TTSResponse,
    TokenInfoResponse,
)
from app.schemas.chat import ChatRequest
from app.schemas.common import IntentType, ActionType
from app.services.workflow_service import process_chat_message
from app.services.voice.stt_service import AICCSTTService, STTError
from app.services.voice.tts_service_google import AICCGoogleTTSService, TTSError

logger = logging.getLogger(__name__)
router = APIRouter()

# 지원하는 오디오 포맷
SUPPORTED_AUDIO_FORMATS = {
    "wav", "mp3", "webm", "ogg", "flac", "m4a", "mp4", "mpeg", "mpga", "oga", "opus"
}


def _validate_audio_file(filename: str) -> None:
    """오디오 파일 포맷 검증"""
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일명이 없습니다."
        )
    
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 오디오 포맷: {ext}. 지원 포맷: {SUPPORTED_AUDIO_FORMATS}"
        )


@router.post("/message", response_model=VoiceChatResponse)
async def voice_chat_message(
    session_id: str = Form(..., description="세션 ID"),
    audio: UploadFile = File(..., description="음성 파일 (wav, mp3, webm 등)"),
    language: str = Form("ko", description="언어 코드"),
    tts_voice: Optional[str] = Form(None, description="TTS 음성 (기본값: 설정된 voice)"),
):
    """
    🎤 음성 채팅 메시지 처리
    
    처리 흐름:
    1. STT: 음성 → 텍스트 (VITO)
    2. 워크플로우: LangGraph 파이프라인 실행
    3. TTS: 텍스트 → 음성 (OpenAI)
    
    Args:
        session_id: 세션 ID (필수)
        audio: 음성 파일 (필수)
        language: 언어 코드 (기본값: ko)
        tts_voice: TTS 음성 종류 (선택)
    
    Returns:
        VoiceChatResponse: AI 응답 (텍스트 + 음성)
    """
    total_start = time.time()
    
    try:
        # 파일 검증
        _validate_audio_file(audio.filename)
        
        # ========== 1. STT: 음성 → 텍스트 ==========
        logger.info(f"[음성채팅] STT 시작 - 세션: {session_id}, 파일: {audio.filename}")
        stt_start = time.time()
        
        audio_bytes = await audio.read()
        
        if len(audio_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="빈 오디오 파일입니다."
            )
        
        try:
            stt_service = AICCSTTService.get_instance()
            stt_result = stt_service.transcribe(audio_bytes, language=language)
        except STTError as e:
            logger.error(f"[음성채팅] STT 실패 - 세션: {session_id}, 오류: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"음성 인식 실패: {str(e)}"
            )
        
        transcribed_text = stt_result.text
        stt_duration = int((time.time() - stt_start) * 1000)
        
        logger.info(f"[음성채팅] STT 완료 - 세션: {session_id}, 텍스트: {transcribed_text[:50]}...")
        
        if not transcribed_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="음성에서 텍스트를 인식할 수 없습니다. 다시 말씀해주세요."
            )
        
        # ========== 2. 워크플로우 실행 ==========
        logger.info(f"[음성채팅] 워크플로우 시작 - 세션: {session_id}")
        
        chat_request = ChatRequest(
            session_id=session_id,
            user_message=transcribed_text,
        )
        chat_response = await process_chat_message(chat_request)
        
        logger.info(f"[음성채팅] 워크플로우 완료 - 세션: {session_id}, intent: {chat_response.intent}")
        
        # ========== 3. TTS: 텍스트 → 음성 ==========
        logger.info(f"[음성채팅] TTS 시작 - 세션: {session_id}")
        tts_start = time.time()
        
        audio_base64: Optional[str] = None
        tts_duration: Optional[int] = None
        
        try:
            tts_service = AICCGoogleTTSService.get_instance()
            tts_audio = tts_service.synthesize(
                chat_response.ai_message,
                voice=tts_voice,
            )
            audio_base64 = base64.b64encode(tts_audio).decode("utf-8")
            tts_duration = int((time.time() - tts_start) * 1000)
            
            logger.info(f"[음성채팅] TTS 완료 - 세션: {session_id}, 크기: {len(tts_audio)} bytes")
            
        except TTSError as e:
            # TTS 실패해도 텍스트 응답은 반환 (graceful degradation)
            logger.warning(f"[음성채팅] TTS 실패 (텍스트만 반환) - 세션: {session_id}, 오류: {e}")
        
        total_duration = int((time.time() - total_start) * 1000)
        
        return VoiceChatResponse(
            ai_message=chat_response.ai_message,
            audio_base64=audio_base64,
            audio_format="mp3",
            intent=chat_response.intent,
            suggested_action=chat_response.suggested_action,
            transcribed_text=transcribed_text,
            stt_duration_ms=stt_duration,
            tts_duration_ms=tts_duration,
            total_duration_ms=total_duration,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[음성채팅] 처리 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 처리 중 오류 발생: {str(e)}"
        )


@router.post("/stt", response_model=STTResponse)
async def stt_only(
    audio: UploadFile = File(..., description="음성 파일"),
    language: str = Form("ko", description="언어 코드"),
    diarize: bool = Form(False, description="화자 분리 여부"),
    speaker_count: Optional[int] = Form(None, description="예상 화자 수"),
):
    """
    🎤 STT 전용 엔드포인트 (테스트/디버깅용)
    
    음성 파일을 텍스트로 변환합니다.
    """
    start_time = time.time()
    
    _validate_audio_file(audio.filename)
    audio_bytes = await audio.read()
    
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 오디오 파일입니다."
        )
    
    try:
        stt_service = AICCSTTService.get_instance()
        result = stt_service.transcribe(
            audio_bytes,
            language=language,
            diarize=diarize,
            speaker_count=speaker_count,
        )
    except STTError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 인식 실패: {str(e)}"
        )
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return STTResponse(
        text=result.text,
        language=result.language,
        segments=[
            STTSegment(
                text=seg.text,
                start=seg.start,
                end=seg.end,
                confidence=seg.confidence,
                speaker=seg.speaker,
            )
            for seg in result.segments
        ],
        duration_ms=duration_ms,
    )


@router.post("/tts", response_model=TTSResponse)
async def tts_only(request: TTSRequest):
    """
    🔊 TTS 전용 엔드포인트 (테스트/디버깅용)

    텍스트를 음성으로 변환합니다.
    """
    try:
        logger.info(f"[TTS] 요청 수신 - 텍스트 길이: {len(request.text)}, format: {request.format}")
        tts_service = AICCGoogleTTSService.get_instance()
        audio_bytes = tts_service.synthesize(
            request.text,
            voice=request.voice,
            format=request.format,
        )
        logger.info(f"[TTS] 성공 - 오디오 크기: {len(audio_bytes)} bytes")
    except TTSError as e:
        logger.error(f"[TTS] TTSError 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 합성 실패: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[TTS] 예기치 않은 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 합성 중 오류 발생: {str(e)}"
        )
    
    return TTSResponse(
        audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
        format=request.format,
        voice=request.voice,
        text_length=len(request.text),
        audio_size_bytes=len(audio_bytes),
    )


@router.post("/tts/stream")
async def tts_stream(request: TTSRequest):
    """
    🔊 TTS 스트리밍 엔드포인트
    
    텍스트를 음성으로 변환하여 바이너리로 직접 반환합니다.
    (Base64 인코딩 없이 직접 오디오 파일로 사용 가능)
    """
    try:
        tts_service = AICCGoogleTTSService.get_instance()
        audio_bytes = tts_service.synthesize(
            request.text,
            voice=request.voice,
            format=request.format,
        )
    except TTSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 합성 실패: {str(e)}"
        )
    
    # MIME 타입 매핑
    mime_types = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
    }
    
    return Response(
        content=audio_bytes,
        media_type=mime_types.get(request.format, f"audio/{request.format}"),
        headers={
            "Content-Disposition": f"attachment; filename=tts_output.{request.format}"
        }
    )


@router.post("/transcribe")
async def transcribe_only(
    audio: UploadFile = File(..., description="음성 파일"),
    language: str = Form("ko", description="언어 코드"),
):
    """
    🎤 STT 전용 엔드포인트 (상담원 대시보드용)

    음성 파일을 텍스트로 변환합니다.
    AI 워크플로우 없이 순수 STT만 수행합니다.
    """
    start_time = time.time()

    _validate_audio_file(audio.filename)
    audio_bytes = await audio.read()

    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 오디오 파일입니다."
        )

    try:
        stt_service = AICCSTTService.get_instance()
        result = stt_service.transcribe(audio_bytes, language=language)
    except STTError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 인식 실패: {str(e)}"
        )

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "transcribed_text": result.text,
        "stt_duration_ms": duration_ms,
    }


@router.get("/token-info", response_model=TokenInfoResponse)
async def get_token_info():
    """
    🔑 VITO STT 토큰 정보 조회 (디버깅용)
    
    현재 VITO API 토큰의 상태를 확인합니다.
    """
    try:
        stt_service = AICCSTTService.get_instance()
        info = stt_service.get_token_info()
        
        return TokenInfoResponse(
            has_token=info["has_token"],
            is_valid=info["is_valid"],
            expiry_datetime=info["expiry_datetime"],
            remaining_seconds=info["remaining_seconds"],
        )
    except STTError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"토큰 정보 조회 실패: {str(e)}"
        )

