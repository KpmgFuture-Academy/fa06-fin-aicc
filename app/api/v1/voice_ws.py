"""WebSocket 실시간 음성 스트리밍 API

실시간 양방향 음성 통신을 위한 WebSocket 엔드포인트.

사용 흐름:
1. 클라이언트가 WebSocket 연결 (/api/v1/voice/ws/{session_id})
2. audio_start 메시지로 음성 전송 시작 알림
3. audio_chunk 메시지로 음성 데이터 청크 전송
4. audio_end 메시지로 음성 전송 종료
5. 서버가 STT → 워크플로우 → TTS 처리 후 응답

메시지 형식:
- 클라이언트 → 서버: JSON {"type": "...", "data": {...}}
- 서버 → 클라이언트: JSON {"type": "...", "data": {...}}
"""

import asyncio
import base64
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.chat import ChatRequest
from app.schemas.voice import WSMessageType
from app.services.workflow_service import process_chat_message
from app.services.voice.stt_service import AICCSTTService, STTError
from app.services.voice.tts_service import AICCTTSService, TTSError

logger = logging.getLogger(__name__)
router = APIRouter()


class VoiceWebSocketManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        # session_id → WebSocket 매핑
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        """연결 수락 및 등록"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"[WS] 연결됨 - 세션: {session_id}")
    
    def disconnect(self, session_id: str):
        """연결 해제"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"[WS] 연결 해제 - 세션: {session_id}")
    
    async def send_json(self, session_id: str, message: dict):
        """JSON 메시지 전송"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)
    
    async def send_message(
        self, 
        session_id: str, 
        msg_type: str, 
        data: Optional[dict] = None
    ):
        """타입이 있는 메시지 전송"""
        message = {
            "type": msg_type,
            "data": data or {},
            "timestamp": time.time(),
        }
        await self.send_json(session_id, message)


# 전역 매니저 인스턴스
ws_manager = VoiceWebSocketManager()


@router.websocket("/ws/{session_id}")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    🎤 실시간 음성 WebSocket 엔드포인트
    
    연결 URL: ws://localhost:8000/api/v1/voice/ws/{session_id}
    
    클라이언트 → 서버 메시지:
    - audio_start: 음성 전송 시작 {"type": "audio_start", "data": {"language": "ko", "tts_voice": "alloy"}}
    - audio_chunk: 음성 데이터 {"type": "audio_chunk", "data": {"audio_base64": "..."}}
    - audio_end: 음성 전송 종료 {"type": "audio_end"}
    - text_message: 텍스트 직접 전송 {"type": "text_message", "data": {"text": "..."}}
    - ping: 연결 확인 {"type": "ping"}
    
    서버 → 클라이언트 메시지:
    - connected: 연결 완료
    - stt_result: STT 결과
    - ai_response: AI 응답
    - tts_audio: TTS 음성
    - error: 에러
    - pong: Ping 응답
    """
    await ws_manager.connect(session_id, websocket)
    
    # 연결 완료 메시지
    await ws_manager.send_message(
        session_id,
        WSMessageType.CONNECTED,
        {"session_id": session_id, "message": "연결되었습니다."}
    )
    
    # 음성 데이터 버퍼
    audio_buffer: list[bytes] = []
    audio_settings: dict = {
        "language": "ko",
        "tts_voice": "alloy",
        "diarize": False,
    }
    
    try:
        while True:
            # 메시지 수신
            raw_message = await websocket.receive()
            
            # 연결 종료 확인
            if raw_message.get("type") == "websocket.disconnect":
                break
            
            # 바이너리 데이터 (직접 오디오 청크)
            if "bytes" in raw_message:
                audio_buffer.append(raw_message["bytes"])
                continue
            
            # JSON 메시지
            if "text" in raw_message:
                try:
                    message = json.loads(raw_message["text"])
                except json.JSONDecodeError:
                    await ws_manager.send_message(
                        session_id,
                        WSMessageType.ERROR,
                        {"error": "잘못된 JSON 형식입니다."}
                    )
                    continue
                
                msg_type = message.get("type", "")
                msg_data = message.get("data", {})
                
                # ========== 메시지 타입별 처리 ==========
                
                if msg_type == WSMessageType.PING:
                    # Ping-Pong
                    await ws_manager.send_message(session_id, WSMessageType.PONG)
                
                elif msg_type == WSMessageType.AUDIO_START:
                    # 음성 전송 시작
                    audio_buffer.clear()
                    audio_settings.update({
                        "language": msg_data.get("language", "ko"),
                        "tts_voice": msg_data.get("tts_voice", "alloy"),
                        "diarize": msg_data.get("diarize", False),
                    })
                    logger.info(f"[WS] 음성 시작 - 세션: {session_id}, 설정: {audio_settings}")
                
                elif msg_type == WSMessageType.AUDIO_CHUNK:
                    # 음성 데이터 청크 (Base64)
                    audio_base64 = msg_data.get("audio_base64", "")
                    if audio_base64:
                        try:
                            audio_bytes = base64.b64decode(audio_base64)
                            audio_buffer.append(audio_bytes)
                        except Exception as e:
                            logger.warning(f"[WS] Base64 디코딩 실패: {e}")
                
                elif msg_type == WSMessageType.AUDIO_END:
                    # 음성 전송 종료 → 처리 시작
                    if audio_buffer:
                        await process_audio_and_respond(
                            session_id=session_id,
                            audio_data=b"".join(audio_buffer),
                            settings=audio_settings,
                        )
                        audio_buffer.clear()
                    else:
                        await ws_manager.send_message(
                            session_id,
                            WSMessageType.ERROR,
                            {"error": "음성 데이터가 없습니다."}
                        )
                
                elif msg_type == WSMessageType.TEXT_MESSAGE:
                    # 텍스트 직접 전송 (STT 건너뛰기)
                    text = msg_data.get("text", "").strip()
                    if text:
                        await process_text_and_respond(
                            session_id=session_id,
                            text=text,
                            tts_voice=audio_settings.get("tts_voice", "alloy"),
                        )
                    else:
                        await ws_manager.send_message(
                            session_id,
                            WSMessageType.ERROR,
                            {"error": "텍스트가 비어있습니다."}
                        )
                
                else:
                    await ws_manager.send_message(
                        session_id,
                        WSMessageType.ERROR,
                        {"error": f"알 수 없는 메시지 타입: {msg_type}"}
                    )
    
    except WebSocketDisconnect:
        logger.info(f"[WS] 클라이언트 연결 종료 - 세션: {session_id}")
    except Exception as e:
        logger.error(f"[WS] 오류 발생 - 세션: {session_id}, 오류: {e}", exc_info=True)
        try:
            await ws_manager.send_message(
                session_id,
                WSMessageType.ERROR,
                {"error": f"서버 오류: {str(e)}"}
            )
        except:
            pass
    finally:
        ws_manager.disconnect(session_id)


async def process_audio_and_respond(
    session_id: str,
    audio_data: bytes,
    settings: dict,
):
    """음성 데이터 처리 및 응답 (STT → 워크플로우 → TTS)"""
    
    try:
        # ========== 1. STT ==========
        logger.info(f"[WS] STT 시작 - 세션: {session_id}, 크기: {len(audio_data)} bytes")
        
        try:
            stt_service = AICCSTTService.get_instance()
            stt_result = stt_service.transcribe(
                audio_data,
                language=settings.get("language", "ko"),
                diarize=settings.get("diarize", False),
            )
            transcribed_text = stt_result.text
        except STTError as e:
            await ws_manager.send_message(
                session_id,
                WSMessageType.ERROR,
                {"error": f"음성 인식 실패: {str(e)}"}
            )
            return
        
        if not transcribed_text.strip():
            await ws_manager.send_message(
                session_id,
                WSMessageType.ERROR,
                {"error": "음성에서 텍스트를 인식할 수 없습니다."}
            )
            return
        
        # STT 결과 전송
        await ws_manager.send_message(
            session_id,
            WSMessageType.STT_RESULT,
            {
                "text": transcribed_text,
                "is_final": True,
                "language": stt_result.language,
            }
        )
        
        # ========== 2. 워크플로우 + TTS ==========
        await process_text_and_respond(
            session_id=session_id,
            text=transcribed_text,
            tts_voice=settings.get("tts_voice", "alloy"),
        )
        
    except Exception as e:
        logger.error(f"[WS] 처리 오류 - 세션: {session_id}, 오류: {e}", exc_info=True)
        await ws_manager.send_message(
            session_id,
            WSMessageType.ERROR,
            {"error": f"처리 중 오류: {str(e)}"}
        )


async def process_text_and_respond(
    session_id: str,
    text: str,
    tts_voice: str = "alloy",
):
    """텍스트 처리 및 응답 (워크플로우 → TTS)"""
    
    try:
        # ========== 워크플로우 실행 ==========
        logger.info(f"[WS] 워크플로우 시작 - 세션: {session_id}, 텍스트: {text[:30]}...")
        
        chat_request = ChatRequest(
            session_id=session_id,
            user_message=text,
        )
        chat_response = await process_chat_message(chat_request)
        
        # AI 응답 전송
        await ws_manager.send_message(
            session_id,
            WSMessageType.AI_RESPONSE,
            {
                "text": chat_response.ai_message,
                "intent": chat_response.intent.value if hasattr(chat_response.intent, 'value') else str(chat_response.intent),
                "suggested_action": chat_response.suggested_action.value if hasattr(chat_response.suggested_action, 'value') else str(chat_response.suggested_action),
            }
        )
        
        # ========== TTS ==========
        logger.info(f"[WS] TTS 시작 - 세션: {session_id}")
        
        try:
            tts_service = AICCTTSService.get_instance()
            tts_audio = tts_service.synthesize(
                chat_response.ai_message,
                voice=tts_voice,
            )
            
            # TTS 음성 전송
            await ws_manager.send_message(
                session_id,
                WSMessageType.TTS_AUDIO,
                {
                    "audio_base64": base64.b64encode(tts_audio).decode("utf-8"),
                    "format": "mp3",
                    "is_final": True,
                }
            )
            
            logger.info(f"[WS] 응답 완료 - 세션: {session_id}")
            
        except TTSError as e:
            logger.warning(f"[WS] TTS 실패 - 세션: {session_id}, 오류: {e}")
            # TTS 실패해도 텍스트 응답은 이미 전송됨
    
    except Exception as e:
        logger.error(f"[WS] 처리 오류 - 세션: {session_id}, 오류: {e}", exc_info=True)
        await ws_manager.send_message(
            session_id,
            WSMessageType.ERROR,
            {"error": f"처리 중 오류: {str(e)}"}
        )


# ========== 연결 상태 확인 API ==========

@router.get("/ws/connections")
async def get_active_connections():
    """현재 활성 WebSocket 연결 목록 (디버깅용)"""
    return {
        "active_sessions": list(ws_manager.active_connections.keys()),
        "count": len(ws_manager.active_connections),
    }

