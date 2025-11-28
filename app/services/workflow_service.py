"""LangGraph 워크플로우 서비스
API에서 워크플로우를 호출하고 상태 변환을 처리하는 서비스
"""

import logging
from typing import Dict, Any
from datetime import datetime
from ai_engine.graph.workflow import build_workflow
from ai_engine.graph.state import GraphState, ConversationMessage
from app.schemas.chat import ChatRequest, ChatResponse, SourceDocument
from app.schemas.handover import HandoverRequest, HandoverResponse, AnalysisResult
from app.schemas.common import IntentType, ActionType, SentimentType, TriageDecisionType
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


# 워크플로우 인스턴스 (싱글톤)
_workflow = None


def get_workflow():
    """워크플로우 인스턴스 가져오기 (싱글톤)"""
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


def chat_request_to_state(request: ChatRequest) -> GraphState:
    """ChatRequest를 GraphState로 변환"""
    # 이전 대화 이력 로드
    conversation_history = session_manager.get_conversation_history(request.session_id)
    
    # 턴 수 계산
    conversation_turn = len([msg for msg in conversation_history if msg.get("role") == "user"])
    
    # DB에서 세션 상태 직접 로드 (추론 대신 정확한 값)
    session_state = session_manager.get_session_state(request.session_id)
    
    state: GraphState = {
        "session_id": request.session_id,
        "user_message": request.user_message,
        "conversation_history": conversation_history,
        "conversation_turn": conversation_turn + 1,  # 현재 턴 포함
        "is_new_turn": True,
        "processing_start_time": datetime.now().isoformat(),
        # HUMAN_REQUIRED 플로우 관련 상태 (DB에서 직접 로드)
        "is_human_required_flow": session_state["is_human_required_flow"],
        "customer_consent_received": session_state["customer_consent_received"],
        "collected_info": session_state["collected_info"],
        "info_collection_complete": session_state["info_collection_complete"],
        # triage_decision도 이전 턴 값 복원 (참고용)
        "triage_decision": session_state["triage_decision"],
    }
    
    return state


def state_to_chat_response(state: GraphState) -> ChatResponse:
    """GraphState를 ChatResponse로 변환
    
    suggested_action 결정:
    - state에 이미 suggested_action이 설정되어 있으면 우선 사용 (예: human_transfer 노드에서 설정)
    - 그 외의 경우:
      - triage_decision이 HUMAN_REQUIRED이거나 requires_consultant가 True면 HANDOVER
      - 그 외의 경우 CONTINUE
    """
    # suggested_action 결정
    # state에 이미 설정된 suggested_action이 있으면 우선 사용 (human_transfer 노드 등에서 설정)
    suggested_action = state.get("suggested_action")
    
    if suggested_action is None:
        # suggested_action이 설정되지 않은 경우에만 결정
        triage_decision = state.get("triage_decision")
        requires_consultant = state.get("requires_consultant", False)
        
        # triage_decision이 HUMAN_REQUIRED이거나 requires_consultant가 True면 HANDOVER
        if triage_decision == TriageDecisionType.HUMAN_REQUIRED or requires_consultant:
            suggested_action = ActionType.HANDOVER
        else:
            suggested_action = ActionType.CONTINUE
    
    # ai_message 설정
    ai_message = state.get("ai_message")
    
    # ai_message가 없으면 상황에 맞는 메시지 설정
    if not ai_message:
        if suggested_action == ActionType.HANDOVER:
            # 상담사 연결인 경우
            ai_message = "상담사 연결이 필요하신 것으로 확인되었습니다. 곧 상담사가 연결될 예정입니다. 잠시만 기다려주세요."
        else:
            # 일반적인 경우 (에러)
            ai_message = "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."
    
    intent = state.get("intent", IntentType.INFO_REQ)
    source_documents = state.get("source_documents", [])
    
    return ChatResponse(
        ai_message=ai_message,
        intent=intent,
        suggested_action=suggested_action,
        source_documents=source_documents
    )


def state_to_handover_response(state: GraphState) -> HandoverResponse:
    """GraphState를 HandoverResponse로 변환"""
    from app.schemas.handover import KMSRecommendation
    
    # human_transfer 노드에서 생성한 handover_analysis_result 사용
    handover_result = state.get("handover_analysis_result")
    
    if handover_result:
        # handover_analysis_result가 있으면 사용
        summary = handover_result.get("summary", "요약 정보가 없습니다.")
        customer_sentiment_str = handover_result.get("customer_sentiment", "NEUTRAL")
        customer_sentiment = SentimentType(customer_sentiment_str) if isinstance(customer_sentiment_str, str) else customer_sentiment_str
        extracted_keywords = handover_result.get("extracted_keywords", [])
        kms_recommendations_raw = handover_result.get("kms_recommendations", [])
    else:
        # 없으면 직접 state에서 가져오기 (fallback)
        summary = state.get("summary", "요약 정보가 없습니다.")
        customer_sentiment = state.get("customer_sentiment", SentimentType.NEUTRAL)
        extracted_keywords = state.get("extracted_keywords", [])
        kms_recommendations_raw = state.get("kms_recommendations", [])
    
    # kms_recommendations를 KMSRecommendation 객체로 변환
    kms_recommendations = []
    for rec in kms_recommendations_raw:
        if isinstance(rec, dict):
            kms_recommendations.append(KMSRecommendation(**rec))
        elif isinstance(rec, KMSRecommendation):
            kms_recommendations.append(rec)
        else:
            # TypedDict인 경우
            kms_recommendations.append(KMSRecommendation(
                title=rec.get("title", ""),
                url=rec.get("url", ""),
                relevance_score=rec.get("relevance_score", 0.0)
            ))
    
    analysis_result = AnalysisResult(
        customer_sentiment=customer_sentiment,
        summary=summary,
        extracted_keywords=extracted_keywords,
        kms_recommendations=kms_recommendations
    )
    
    return HandoverResponse(
        status="success",
        analysis_result=analysis_result
    )


async def process_chat_message(request: ChatRequest) -> ChatResponse:
    """채팅 메시지 처리 (LangGraph 워크플로우 실행)"""
    try:
        logger.info(f"워크플로우 시작 - 세션: {request.session_id}")
        
        # ChatRequest를 GraphState로 변환
        initial_state = chat_request_to_state(request)
        logger.debug(f"초기 상태 생성 완료 - 대화 이력 수: {len(initial_state.get('conversation_history', []))}")
        
        # 워크플로우 실행
        workflow = get_workflow()
        final_state = await workflow.ainvoke(initial_state)
        
        # 에러 확인 및 로깅
        metadata = final_state.get("metadata", {})
        if metadata:
            if "answer_error" in metadata:
                logger.error(f"답변 생성 노드 오류 - 세션: {request.session_id}, 오류: {metadata['answer_error']}")
            if "decision_error" in metadata:
                logger.error(f"Triage 에이전트 노드 오류 - 세션: {request.session_id}, 오류: {metadata['decision_error']}")
            if "summary_error" in metadata:
                logger.error(f"요약 에이전트 노드 오류 - 세션: {request.session_id}, 오류: {metadata['summary_error']}")
            if "intent_error" in metadata:
                logger.warning(f"의도 분류 Tool 오류 (키워드 기반 fallback 사용) - 세션: {request.session_id}, 오류: {metadata['intent_error']}")
            if "rag_error" in metadata:
                logger.warning(f"RAG 검색 Tool 오류 (빈 결과 반환) - 세션: {request.session_id}, 오류: {metadata['rag_error']}")
        
        # DB 저장 상태 확인
        db_stored = final_state.get("db_stored", False)
        if not db_stored:
            # 상담사 연결 경로인 경우 DB 저장이 없을 수 있음 (이제는 저장됨)
            error_message = final_state.get('error_message', 'Unknown')
            if error_message and error_message != 'Unknown':
                logger.warning(f"DB 저장 실패 - 세션: {request.session_id}, 오류: {error_message}")
            else:
                logger.debug(f"DB 저장 상태 확인 - 세션: {request.session_id}, 저장됨: {db_stored}")
        
        # conversation_history는 chat_db_storage_node에서 이미 DB에 저장됨
        # 별도 저장 불필요
        
        # GraphState를 ChatResponse로 변환
        response = state_to_chat_response(final_state)
        
        # AI 메시지에 에러가 포함되어 있는지 확인
        ai_message = final_state.get("ai_message", "")
        if "오류" in ai_message or "error" in ai_message.lower() or "죄송합니다" in ai_message:
            logger.warning(f"워크플로우 완료 (에러 포함) - 세션: {request.session_id}, 메시지: {ai_message[:100]}")
        
        logger.info(f"워크플로우 완료 - 세션: {request.session_id}, intent: {response.intent}, action: {response.suggested_action}")
        
        return response
        
    except Exception as e:
        logger.error(f"워크플로우 실행 중 오류 - 세션: {request.session_id}, 오류: {str(e)}", exc_info=True)
        # 에러 발생 시 기본 응답 반환
        return ChatResponse(
            ai_message="죄송합니다. 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            intent=IntentType.INFO_REQ,
            suggested_action=ActionType.CONTINUE,
            source_documents=[]
        )


async def process_handover(request: HandoverRequest) -> HandoverResponse:
    """상담원 이관 처리 (LangGraph 워크플로우 실행)"""
    try:
        logger.info(f"상담원 이관 워크플로우 시작 - 세션: {request.session_id}, 사유: {request.trigger_reason}")
        
        # 이전 대화 이력 로드
        conversation_history = session_manager.get_conversation_history(request.session_id)
        
        if not conversation_history:
            logger.warning(f"대화 이력 없음 - 세션: {request.session_id}")
            # 대화 이력이 없으면 에러
            return HandoverResponse(
                status="error",
                analysis_result=AnalysisResult(
                    customer_sentiment=SentimentType.NEUTRAL,
                    summary="대화 이력이 없어 요약을 생성할 수 없습니다.",
                    extracted_keywords=[],
                    kms_recommendations=[]
                )
            )
        
        logger.info(f"대화 이력 로드 완료 - 세션: {request.session_id}, 메시지 수: {len(conversation_history)}")
        
        # GraphState 생성 (상담원 이관 요청)
        # 상담원 이관 요청은 직접 요청이므로 triage_agent를 거치지 않고 바로 처리
        initial_state: GraphState = {
            "session_id": request.session_id,
            "user_message": f"[상담원 이관 요청] {request.trigger_reason}",
            "conversation_history": conversation_history,
            "triage_decision": TriageDecisionType.HUMAN_REQUIRED,  # 상담원 이관 요청
            "requires_consultant": True,
            "handover_reason": request.trigger_reason,
            "customer_intent_summary": None,  # triage_agent를 거치지 않으므로 None
            "intent": IntentType.HUMAN_REQ,
            "processing_start_time": datetime.now().isoformat(),
            # 상담원 이관 요청은 정보 수집 플로우와 별개 (직접 이관)
            "is_human_required_flow": False,
            "customer_consent_received": False,
            "collected_info": {},
            "info_collection_complete": False,
        }
        
        # 워크플로우 실행
        # 현재는 모든 케이스가 answer_agent를 거치지만, 상담원 이관 요청의 경우
        # summary_agent와 human_transfer가 필요한 경우를 위해 별도 처리 고려 가능
        workflow = get_workflow()
        final_state = await workflow.ainvoke(initial_state)
        
        # GraphState를 HandoverResponse로 변환
        response = state_to_handover_response(final_state)
        
        logger.info(f"상담원 이관 워크플로우 완료 - 세션: {request.session_id}, 상태: {response.status}")
        
        return response
        
    except Exception as e:
        logger.error(f"상담원 이관 워크플로우 실행 중 오류 - 세션: {request.session_id}, 오류: {str(e)}", exc_info=True)
        # 에러 발생 시 기본 응답 반환
        return HandoverResponse(
            status="error",
            analysis_result=AnalysisResult(
                customer_sentiment=SentimentType.NEUTRAL,
                summary="처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                extracted_keywords=[],
                kms_recommendations=[]
            )
        )

