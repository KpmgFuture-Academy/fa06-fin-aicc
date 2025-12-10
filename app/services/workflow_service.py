"""LangGraph 워크플로우 서비스
API에서 워크플로우를 호출하고 상태 변환을 처리하는 서비스

## 입력 검증 레이어 (External Validation Layer)
====================================================
LangGraph 워크플로우 진입 전에 입력을 검증하여 시스템 안정성을 보장합니다.

### 검증 항목:
1. 빈 입력 검증: 2자 미만의 입력은 조기 반환
2. 매우 긴 입력 검증: 2000자 초과 입력은 조기 반환
3. (LangGraph 내부에서 처리): RAG/Intent 실패, LLM API 오류 등

### 동작 방식:
- validate_input() 함수가 입력을 검증
- 유효하지 않은 입력은 LangGraph 워크플로우를 실행하지 않고 즉시 응답 반환
- 유효한 입력만 LangGraph 워크플로우로 전달

### 변경 이력:
- 2025-12-09: 입력 검증 레이어 추가 (빈 입력, 매우 긴 입력 처리)
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from ai_engine.graph.workflow import build_workflow
from ai_engine.graph.state import GraphState, ConversationMessage
from app.schemas.chat import ChatRequest, ChatResponse, SourceDocument
from app.schemas.handover import HandoverRequest, HandoverResponse, AnalysisResult
from app.schemas.common import IntentType, ActionType, SentimentType, TriageDecisionType
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


# ============================================================
# 입력 검증 레이어 (External Validation Layer)
# ============================================================

# 검증 설정 상수
MIN_INPUT_LENGTH = 2       # 최소 입력 길이 (2자 미만은 빈 입력으로 처리)
MAX_INPUT_LENGTH = 2000    # 최대 입력 길이 (2000자 초과는 너무 긴 입력으로 처리)


@dataclass
class ValidationResult:
    """입력 검증 결과"""
    is_valid: bool
    error_type: Optional[str] = None  # "empty", "too_long", None
    error_message: Optional[str] = None


def validate_input(user_message: str) -> ValidationResult:
    """
    사용자 입력 검증 (LangGraph 워크플로우 진입 전 외부 검증)

    Args:
        user_message: 사용자 입력 메시지

    Returns:
        ValidationResult: 검증 결과

    검증 항목:
        1. 빈 입력 검증: None, 빈 문자열, 공백만 있는 문자열, 2자 미만
        2. 매우 긴 입력 검증: 2000자 초과

    Note:
        - 이 검증은 LangGraph 워크플로우 외부에서 수행됩니다.
        - LangGraph 내부의 RAG/Intent 실패, LLM API 오류 등은
          각 노드에서 별도로 처리됩니다.
    """
    # 1. 빈 입력 검증
    if not user_message or not user_message.strip():
        return ValidationResult(
            is_valid=False,
            error_type="empty",
            error_message="메시지를 입력해 주세요."
        )

    # 공백 제거 후 길이 확인
    stripped_message = user_message.strip()

    # 2. 너무 짧은 입력 검증 (2자 미만)
    if len(stripped_message) < MIN_INPUT_LENGTH:
        return ValidationResult(
            is_valid=False,
            error_type="empty",
            error_message="메시지를 입력해 주세요."
        )

    # 3. 매우 긴 입력 검증 (2000자 초과)
    if len(stripped_message) > MAX_INPUT_LENGTH:
        return ValidationResult(
            is_valid=False,
            error_type="too_long",
            error_message=f"입력이 너무 깁니다. {MAX_INPUT_LENGTH}자 이하로 입력해 주세요. (현재: {len(stripped_message)}자)"
        )

    # 모든 검증 통과
    return ValidationResult(is_valid=True)


def create_validation_error_response(validation_result: ValidationResult) -> ChatResponse:
    """
    검증 실패 시 즉시 반환할 ChatResponse 생성

    Args:
        validation_result: 검증 실패 결과

    Returns:
        ChatResponse: 에러 응답
    """
    return ChatResponse(
        ai_message=validation_result.error_message,
        intent=IntentType.INFO_REQ,
        suggested_action=ActionType.CONTINUE,
        source_documents=[]
    )


# ============================================================
# 워크플로우 관리
# ============================================================

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
        info_collection_complete = state.get("info_collection_complete", False)
        is_human_required_flow = state.get("is_human_required_flow", False)
        
        # 정보 수집 중인지 확인 (HUMAN_REQUIRED 플로우 + 정보 수집 미완료)
        if is_human_required_flow and not info_collection_complete:
            # 정보 수집 중에는 CONTINUE (리포트 생성하지 않음)
            suggested_action = ActionType.CONTINUE
        # triage_decision이 HUMAN_REQUIRED이고 정보 수집이 완료되었거나, requires_consultant가 True면 HANDOVER
        elif (triage_decision == TriageDecisionType.HUMAN_REQUIRED and info_collection_complete) or requires_consultant:
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
    info_collection_complete = state.get("info_collection_complete", False)

    return ChatResponse(
        ai_message=ai_message,
        intent=intent,
        suggested_action=suggested_action,
        source_documents=source_documents,
        info_collection_complete=info_collection_complete
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
    """채팅 메시지 처리 (LangGraph 워크플로우 실행)

    처리 흐름:
        1. 입력 검증 (External Validation Layer)
           - 빈 입력 검증 (2자 미만)
           - 매우 긴 입력 검증 (2000자 초과)
           - 검증 실패 시 LangGraph 워크플로우를 실행하지 않고 즉시 응답 반환

        2. LangGraph 워크플로우 실행
           - triage_agent → answer_agent → chat_db_storage
           - 내부적으로 RAG/Intent 실패, LLM API 오류 등 처리
    """
    try:
        logger.info(f"워크플로우 시작 - 세션: {request.session_id}")

        # ============================================================
        # Step 1: 입력 검증 (External Validation Layer)
        # ============================================================
        validation_result = validate_input(request.user_message)

        if not validation_result.is_valid:
            logger.warning(
                f"입력 검증 실패 - 세션: {request.session_id}, "
                f"유형: {validation_result.error_type}, "
                f"메시지 길이: {len(request.user_message) if request.user_message else 0}"
            )
            # 검증 실패 시 LangGraph 워크플로우를 실행하지 않고 즉시 응답 반환
            return create_validation_error_response(validation_result)

        logger.debug(f"입력 검증 통과 - 세션: {request.session_id}")

        # ============================================================
        # Step 2: LangGraph 워크플로우 실행
        # ============================================================
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
        
        # 요약 정보가 생성되었으면 session_manager에 저장 (handover에서 재사용)
        summary = final_state.get("summary")
        sentiment = final_state.get("customer_sentiment")
        keywords = final_state.get("extracted_keywords", [])
        if summary or sentiment or keywords:
            session_manager.store_session_metadata(
                request.session_id, 
                summary, 
                sentiment.value if sentiment else None,
                keywords
            )
            logger.debug(f"요약 정보 저장 완료 - 세션: {request.session_id}")
        
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
    """상담원 이관 처리 (summary_agent 직접 호출)
    
    "상담원 연결" 버튼 클릭 시 호출되며, 대화 내용을 요약하고 분석 결과를 반환합니다.
    워크플로우를 거치지 않고 직접 summary_agent를 호출하여 요약/감정/키워드를 생성합니다.
    """
    from ai_engine.graph.nodes.summary_agent import summary_agent_node
    
    try:
        logger.info(f"상담원 이관 분석 시작 - 세션: {request.session_id}, 사유: {request.trigger_reason}")
        
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
        
        # 이전 워크플로우에서 생성된 요약 정보 가져오기
        metadata = session_manager.get_session_metadata(request.session_id)
        stored_summary = metadata.get("summary")
        stored_sentiment = metadata.get("sentiment")
        stored_keywords = metadata.get("keywords", [])
        
        if stored_summary:
            logger.info(f"저장된 요약 정보 발견 - 세션: {request.session_id}, summary: {stored_summary[:50]}...")
        else:
            logger.warning(f"저장된 요약 정보 없음 - 세션: {request.session_id}, 워크플로우에서 새로 생성 예정")
        
        # GraphState 생성 (상담원 이관 요청)
        # 상담원 이관 요청은 직접 요청이므로 triage_agent를 거치지 않고 바로 처리
        initial_state: GraphState = {
            "session_id": request.session_id,
            "conversation_history": conversation_history,
            "handover_reason": request.trigger_reason,
            "intent": IntentType.HUMAN_REQ,
            "processing_start_time": datetime.now().isoformat(),
            # 상담원 이관 요청은 정보 수집과 별개
            "is_collecting_info": False,
            "info_collection_count": 0,
            # 상담원 이관 요청은 정보 수집 플로우와 별개 (직접 이관)
            "is_human_required_flow": False,
            "customer_consent_received": False,
            "collected_info": {},
            "info_collection_complete": False,
            # 🔧 이전 워크플로우에서 생성된 요약 정보 포함
            "summary": stored_summary,
            "customer_sentiment": SentimentType(stored_sentiment) if stored_sentiment else None,
            "extracted_keywords": stored_keywords,
        }
        
        # summary_agent 직접 호출 - 요약/감정/키워드 생성
        state = summary_agent_node(initial_state)
        
        logger.info(f"요약 생성 완료 - 세션: {request.session_id}, 요약: {state.get('summary', 'None')[:50] if state.get('summary') else 'None'}...")
        
        # GraphState를 HandoverResponse로 변환
        response = state_to_handover_response(state)
        
        logger.info(f"상담원 이관 분석 완료 - 세션: {request.session_id}, 상태: {response.status}")
        
        return response
        
    except Exception as e:
        logger.error(f"상담원 이관 분석 중 오류 - 세션: {request.session_id}, 오류: {str(e)}", exc_info=True)
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
