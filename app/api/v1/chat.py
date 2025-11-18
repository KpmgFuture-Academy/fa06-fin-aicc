# 채팅 담당 직원 - LangGraph 워크플로우 연결

import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.workflow_service import process_chat_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def chat_message(request: ChatRequest):
    """
    고객 메시지를 받아 LangGraph 워크플로우를 통해 처리하고 응답을 반환
    
    - **session_id**: 세션 ID (필수)
    - **user_message**: 사용자 메시지 (필수)
    
    처리 흐름:
    1. DB에서 이전 대화 이력 로드
    2. LangGraph 워크플로우 실행
    3. DB에 메시지 저장
    4. 응답 반환
    """
    logger.info(f"=== API 엔드포인트 도달: /api/v1/chat/message ===")
    logger.info(f"요청 본문: session_id={request.session_id}, user_message={request.user_message[:50]}")
    try:
        # 입력 검증
        if not request.session_id or not request.session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id는 필수입니다."
            )
        
        if not request.user_message or not request.user_message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_message는 필수입니다."
            )
        
        logger.info(f"채팅 메시지 수신 - 세션: {request.session_id}, 메시지: {request.user_message[:50]}")
        
        # 워크플로우 실행
        response = await process_chat_message(request)
        
        # 응답 메시지 확인
        if "오류" in response.ai_message or "error" in response.ai_message.lower() or "죄송합니다" in response.ai_message:
            logger.warning(f"채팅 메시지 처리 완료 (에러 응답) - 세션: {request.session_id}, 응답: {response.ai_message[:100]}")
        else:
            logger.info(f"채팅 메시지 처리 완료 - 세션: {request.session_id}, intent: {response.intent}, action: {response.suggested_action}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"채팅 메시지 처리 중 오류 발생 - 세션: {request.session_id}, 오류: {str(e)}", exc_info=True)
        # 에러 발생 시에도 응답 반환 (워크플로우 서비스에서 처리)
        return await process_chat_message(request)