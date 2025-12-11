"""세션 관리 API - 상담원 대시보드용"""

import json
import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.models.chat_message import ChatSession, ChatMessage, MessageRole

logger = logging.getLogger(__name__)
router = APIRouter()

# 한국 시간(KST, UTC+9) 헬퍼 함수
KST = timezone(timedelta(hours=9))

def get_kst_now() -> datetime:
    """현재 한국 시간 반환"""
    return datetime.now(KST).replace(tzinfo=None)


# ========== Pydantic 스키마 ==========

class HandoverSessionResponse(BaseModel):
    """이관 대기 세션 응답"""
    session_id: str
    created_at: str
    updated_at: str
    collected_info: dict
    handover_status: Optional[str] = None  # pending, accepted, declined, timeout
    handover_accepted_at: Optional[str] = None  # 상담사 수락 시간

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """메시지 응답"""
    id: int
    role: str
    message: str
    created_at: str

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    """메시지 전송 요청"""
    message: str


class SendMessageResponse(BaseModel):
    """메시지 전송 응답"""
    success: bool
    message_id: int
    created_at: str


class AcceptSessionRequest(BaseModel):
    """세션 수락 요청"""
    agent_id: Optional[str] = None  # 상담사 ID (선택사항)


class HandoverStatusResponse(BaseModel):
    """핸드오버 상태 응답"""
    session_id: str
    handover_status: Optional[str] = None  # pending, accepted, declined, timeout
    handover_requested_at: Optional[str] = None
    handover_accepted_at: Optional[str] = None
    assigned_agent_id: Optional[str] = None


# ========== API 엔드포인트 ==========

@router.get("/handover", response_model=List[HandoverSessionResponse])
async def get_handover_sessions():
    """
    이관 대기 중인 세션 목록 조회

    - suggested_action이 'HANDOVER'인 메시지가 있는 활성 세션 조회
    - 상담원 대시보드에서 이관 대기 고객 목록 표시용
    """
    db = SessionLocal()
    try:
        # HANDOVER 상태인 세션 조회
        # 1. 활성 세션 중
        # 2. suggested_action이 'HANDOVER'인 메시지가 있는 세션
        handover_sessions = db.query(ChatSession).join(
            ChatMessage,
            ChatSession.session_id == ChatMessage.session_id
        ).filter(
            ChatSession.is_active == 1,
            ChatMessage.suggested_action == "HANDOVER"
        ).distinct().all()

        result = []
        for session in handover_sessions:
            # collected_info JSON 파싱
            collected_info = {}
            if session.collected_info:
                try:
                    collected_info = json.loads(session.collected_info)
                except json.JSONDecodeError:
                    collected_info = {}

            result.append(HandoverSessionResponse(
                session_id=session.session_id,
                created_at=session.created_at.isoformat(),
                updated_at=session.updated_at.isoformat(),
                collected_info=collected_info,
                handover_status=session.handover_status,
                handover_accepted_at=session.handover_accepted_at.isoformat() if session.handover_accepted_at else None
            ))

        # 로그 레벨을 DEBUG로 변경하여 불필요한 로그 줄이기 (변경 사항이 있을 때만 INFO)
        logger.debug(f"이관 대기 세션 조회: {len(result)}개")
        return result

    except Exception as e:
        logger.error(f"이관 대기 세션 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 조회 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.get("/closed", response_model=List[HandoverSessionResponse])
async def get_closed_sessions():
    """
    종료된 세션 목록 조회 (상담 기록)

    - is_active가 0인 세션 조회
    - 상담원 대시보드에서 과거 상담 기록 조회용
    """
    db = SessionLocal()
    try:
        # 종료된 세션 조회 (is_active == 0)
        closed_sessions = db.query(ChatSession).filter(
            ChatSession.is_active == 0
        ).order_by(ChatSession.updated_at.desc()).all()

        result = []
        for session in closed_sessions:
            # collected_info JSON 파싱
            collected_info = {}
            if session.collected_info:
                try:
                    collected_info = json.loads(session.collected_info)
                except json.JSONDecodeError:
                    collected_info = {}

            result.append(HandoverSessionResponse(
                session_id=session.session_id,
                created_at=session.created_at.isoformat(),
                updated_at=session.updated_at.isoformat(),
                collected_info=collected_info,
                handover_status=session.handover_status,
                handover_accepted_at=session.handover_accepted_at.isoformat() if session.handover_accepted_at else None
            ))

        logger.info(f"종료된 세션 조회: {len(result)}개")
        return result

    except Exception as e:
        logger.error(f"종료된 세션 조회 실패: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 조회 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str,
    after_id: Optional[int] = None,
    after_handover: bool = False
):
    """
    세션의 메시지 목록 조회 (폴링용)

    - **session_id**: 세션 ID
    - **after_id**: 이 ID 이후의 메시지만 조회 (폴링 시 사용)
    - **after_handover**: True면 HANDOVER 이후 메시지만 조회 (상담원 대시보드용)

    상담원/고객 모두 이 API로 새 메시지를 폴링
    """
    db = SessionLocal()
    try:
        # 세션 존재 확인 (is_active 조건 제거 - 상담 중에도 폴링 필요)
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # after_handover가 True면 HANDOVER 이후 메시지만 조회
        handover_message_id = None
        if after_handover:
            handover_msg = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id,
                ChatMessage.suggested_action == "HANDOVER"
            ).order_by(ChatMessage.id.desc()).first()

            if handover_msg:
                handover_message_id = handover_msg.id
                logger.info(f"HANDOVER 메시지 발견 - 세션: {session_id}, ID: {handover_message_id}")

        # 메시지 조회
        query = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        )

        # after_handover가 True이고 HANDOVER 메시지가 있으면 그 이후만 (HANDOVER 메시지 제외)
        if handover_message_id is not None:
            query = query.filter(ChatMessage.id > handover_message_id)

        # after_id가 있으면 해당 ID 이후 메시지만
        if after_id is not None:
            query = query.filter(ChatMessage.id > after_id)

        messages = query.order_by(ChatMessage.created_at.asc()).all()

        result = []
        for msg in messages:
            result.append(MessageResponse(
                id=msg.id,
                role=msg.role.value if isinstance(msg.role, MessageRole) else msg.role,
                message=msg.message,
                created_at=msg.created_at.isoformat()
            ))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"메시지 조회 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메시지 조회 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.post("/{session_id}/customer-message", response_model=SendMessageResponse)
async def send_customer_message(session_id: str, request: SendMessageRequest):
    """
    고객 메시지 전송 (고객 → 상담원)

    - **session_id**: 세션 ID
    - **message**: 전송할 메시지 내용

    상담원 연결 상태에서 고객이 메시지를 보낼 때 사용
    AI 응답 없이 메시지만 DB에 저장
    상담원은 폴링으로 이 메시지를 받아감
    """
    db = SessionLocal()
    try:
        # 세션 존재 확인
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == 1
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 메시지 저장 (role: user로 저장 - 고객 메시지)
        new_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.USER,
            message=request.message,
            created_at=get_kst_now()
        )

        db.add(new_message)
        db.commit()
        db.refresh(new_message)

        logger.info(f"고객 메시지 전송 (상담원 연결 모드) - 세션: {session_id}, 메시지 ID: {new_message.id}")

        return SendMessageResponse(
            success=True,
            message_id=new_message.id,
            created_at=new_message.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"고객 메시지 전송 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메시지 전송 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.post("/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: str, request: SendMessageRequest):
    """
    세션에 메시지 전송 (상담원 → 고객)

    - **session_id**: 세션 ID
    - **message**: 전송할 메시지 내용

    상담원이 고객에게 메시지를 보낼 때 사용
    고객은 폴링으로 이 메시지를 받아감
    """
    db = SessionLocal()
    try:
        # 세션 존재 확인
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == 1
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 메시지 저장 (role: assistant로 저장 - 상담원도 assistant 역할)
        new_message = ChatMessage(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            message=request.message,
            created_at=get_kst_now()
        )

        db.add(new_message)
        db.commit()
        db.refresh(new_message)

        logger.info(f"상담원 메시지 전송 - 세션: {session_id}, 메시지 ID: {new_message.id}")

        return SendMessageResponse(
            success=True,
            message_id=new_message.id,
            created_at=new_message.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"메시지 전송 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메시지 전송 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.get("/{session_id}/all-messages", response_model=List[MessageResponse])
async def get_all_session_messages(session_id: str):
    """
    세션의 전체 메시지 조회 (상담 기록용)

    - 종료된 세션 포함, 모든 메시지 조회
    - 상담원 대시보드에서 과거 상담 내용 확인용
    """
    db = SessionLocal()
    try:
        # 세션 존재 확인 (종료된 세션도 조회)
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 전체 메시지 조회
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        result = []
        for msg in messages:
            result.append(MessageResponse(
                id=msg.id,
                role=msg.role.value if isinstance(msg.role, MessageRole) else msg.role,
                message=msg.message,
                created_at=msg.created_at.isoformat()
            ))

        logger.info(f"세션 전체 메시지 조회 - 세션: {session_id}, 메시지 수: {len(result)}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"메시지 조회 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메시지 조회 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.post("/{session_id}/close")
async def close_session(session_id: str):
    """
    세션 종료 (상담 완료)

    - **session_id**: 세션 ID

    상담원이 상담을 종료할 때 사용
    is_active를 0으로 설정하여 이관 대기 목록에서 제거
    """
    db = SessionLocal()
    try:
        # 세션 존재 확인
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 세션 비활성화
        session.is_active = 0
        session.updated_at = get_kst_now()
        db.commit()

        logger.info(f"세션 종료 - 세션: {session_id}")

        return {"success": True, "message": "세션이 종료되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"세션 종료 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 종료 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


# ========== 핸드오버 상태 관리 API ==========

@router.get("/{session_id}/handover-status", response_model=HandoverStatusResponse)
async def get_handover_status(session_id: str):
    """
    핸드오버 상태 조회 (voice-chatbot 폴링용)

    - **session_id**: 세션 ID

    voice-chatbot에서 상담사 수락 여부를 폴링할 때 사용
    """
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        return HandoverStatusResponse(
            session_id=session.session_id,
            handover_status=session.handover_status,
            handover_requested_at=session.handover_requested_at.isoformat() if session.handover_requested_at else None,
            handover_accepted_at=session.handover_accepted_at.isoformat() if session.handover_accepted_at else None,
            assigned_agent_id=session.assigned_agent_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"핸드오버 상태 조회 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"핸드오버 상태 조회 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.post("/{session_id}/request-handover")
async def request_handover(session_id: str):
    """
    핸드오버 요청 (voice-chatbot → 백엔드)

    - **session_id**: 세션 ID

    고객이 상담원 연결을 요청하면 호출
    handover_status를 'pending'으로 설정
    """
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == 1
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 핸드오버 상태를 pending으로 설정
        session.handover_status = "pending"
        session.handover_requested_at = get_kst_now()
        session.updated_at = get_kst_now()
        db.commit()

        logger.info(f"핸드오버 요청 - 세션: {session_id}, 상태: pending")

        return {
            "success": True,
            "message": "현재 응대 가능한 상담사가 있는지 확인 중입니다. 잠시만 기다려 주시기 바랍니다.",
            "handover_status": "pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"핸드오버 요청 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"핸드오버 요청 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.post("/{session_id}/accept")
async def accept_session(session_id: str, request: AcceptSessionRequest = None):
    """
    세션 수락 (상담사 → 백엔드)

    - **session_id**: 세션 ID
    - **agent_id**: 상담사 ID (선택사항)

    상담사가 세션을 수락하면 호출
    handover_status를 'accepted'로 변경
    """
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == 1
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 이미 다른 상담사가 수락한 경우
        if session.handover_status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 다른 상담사가 수락한 세션입니다."
            )

        # 핸드오버 상태를 accepted로 변경
        session.handover_status = "accepted"
        session.handover_accepted_at = get_kst_now()
        if request and request.agent_id:
            session.assigned_agent_id = request.agent_id
        session.updated_at = get_kst_now()
        db.commit()

        logger.info(f"세션 수락 - 세션: {session_id}, 상담사: {request.agent_id if request else 'unknown'}")

        return {
            "success": True,
            "message": "세션을 수락했습니다.",
            "handover_status": "accepted"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"세션 수락 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 수락 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()


@router.post("/{session_id}/decline")
async def decline_session(session_id: str):
    """
    세션 거절 (상담사 → 백엔드)

    - **session_id**: 세션 ID

    상담사가 세션을 거절하면 호출
    handover_status를 다시 'pending'으로 변경 (다른 상담사가 수락 가능)
    """
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.is_active == 1
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )

        # 핸드오버 상태를 다시 pending으로 변경
        session.handover_status = "pending"
        session.assigned_agent_id = None
        session.updated_at = get_kst_now()
        db.commit()

        logger.info(f"세션 거절 - 세션: {session_id}, 상태: pending (재할당 대기)")

        return {
            "success": True,
            "message": "세션을 거절했습니다. 다른 상담사가 수락할 수 있습니다.",
            "handover_status": "pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"세션 거절 실패 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 거절 중 오류 발생: {str(e)}"
        )
    finally:
        db.close()
