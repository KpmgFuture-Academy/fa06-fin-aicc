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
                collected_info=collected_info
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
                collected_info=collected_info
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
