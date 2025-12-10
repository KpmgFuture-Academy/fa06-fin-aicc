# 상담원 이관 담당 직원 - LangGraph 워크플로우를 통해 요약 리포트 생성

import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.handover import HandoverRequest, HandoverResponse
from app.services.workflow_service import process_handover
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/request", response_model=HandoverResponse)
@router.post("/analyze", response_model=HandoverResponse)
async def analyze_handover(request: HandoverRequest):
    """
    상담원 이관 요청을 받아 LangGraph 워크플로우를 통해 요약 및 분석 결과를 반환
    
    - **session_id**: 세션 ID (필수)
    - **trigger_reason**: 이관 사유 (필수)
    
    처리 흐름:
    1. DB에서 세션의 전체 대화 이력 로드
    2. summary_agent를 통해 요약 생성
    3. 감정 분석 및 키워드 추출
    4. KMS 문서 추천
    5. HandoverResponse 반환
    """
    try:
        # 입력 검증
        if not request.session_id or not request.session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id는 필수입니다."
            )
        
        if not request.trigger_reason or not request.trigger_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="trigger_reason은 필수입니다."
            )
        
        logger.info(f"상담원 이관 요청 수신 - 세션: {request.session_id}, 사유: {request.trigger_reason}")
        
        # 세션 존재 여부 확인
        conversation_history = session_manager.get_conversation_history(request.session_id)
        if not conversation_history:
            logger.warning(f"대화 이력이 없는 세션 - 세션: {request.session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 세션의 대화 이력을 찾을 수 없습니다. 먼저 채팅을 시작해주세요."
            )
        
        logger.info(f"대화 이력 로드 완료 - 세션: {request.session_id}, 메시지 수: {len(conversation_history)}")
        
        # 워크플로우 실행
        response = await process_handover(request)
        
        logger.info(f"상담원 이관 처리 완료 - 세션: {request.session_id}, 상태: {response.status}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상담원 이관 처리 중 오류 발생 - 세션: {request.session_id}, 오류: {str(e)}", exc_info=True)
        # 에러 발생 시 에러 응답 반환 (중복 호출 방지)
        from app.schemas.handover import AnalysisResult
        from app.schemas.common import SentimentType
        return HandoverResponse(
            status="error",
            analysis_result=AnalysisResult(
                customer_sentiment=SentimentType.NEUTRAL,
                summary=f"이관 처리 중 오류가 발생했습니다: {str(e)}",
                extracted_keywords=[],
                kms_recommendations=[]
            )
        )