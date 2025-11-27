# ai_engine/graph/nodes/triage_agent.py

from __future__ import annotations
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from app.core.config import settings
from ai_engine.graph.tools import intent_classification_tool, rag_search_tool, chat_history_tool
from ai_engine.graph.tools.rag_search_tool import parse_rag_result
from app.schemas.common import IntentType, TriageDecisionType

logger = logging.getLogger(__name__)

# LM Studio 또는 OpenAI 사용
if settings.use_lm_studio:
    llm = ChatOpenAI(
        model=settings.lm_studio_model,
        temperature=0.2,
        base_url=settings.lm_studio_base_url,
        api_key="lm-studio",  # LM Studio는 API 키가 필요 없지만 호환성을 위해 더미 값 사용
        timeout=settings.llm_timeout  # 타임아웃 설정 (초)
    )
    logger.info(f"LM Studio 사용 - 모델: {settings.lm_studio_model}, URL: {settings.lm_studio_base_url}, 타임아웃: {settings.llm_timeout}초")
else:
    # OpenAI API 키는 .env 파일에서만 가져옴
    if not settings.openai_api_key:
        raise ValueError(
            "❌ OpenAI API 키가 설정되지 않았습니다!\n"
            "   .env 파일에 OPENAI_API_KEY=sk-... 를 추가해주세요.\n"
            "   프로젝트 루트 디렉토리에 .env 파일이 있는지 확인하세요."
        )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=settings.openai_api_key,  # .env 파일에서만 가져옴
        timeout=60  # OpenAI는 빠르므로 60초
    )
    logger.info(f"✅ OpenAI API 사용 - .env 파일에서 API 키 로드: {settings.openai_api_key[:20]}... (길이: {len(settings.openai_api_key)} 문자)")


def triage_agent_node(state: GraphState) -> GraphState:
    """고객 질문을 판단하여 처리 방식을 결정하는 노드.
    
    intent_classification_tool과 rag_search_tool을 직접 호출하여 
    의도 분류와 RAG 검색 결과를 얻은 후, 그 결과를 기반으로 다음 중 하나를 결정합니다:
    - AUTO_HANDLE_OK: 자동 처리 가능 (답변 생성)
    - NEED_MORE_INFO: 추가 정보 필요 (질문 생성)
    - HUMAN_REQUIRED: 상담사 연결 필요
    """
    user_message = state["user_message"]
    
    try:
        # 정보 수집 단계면 Tool 사용 안 하고 바로 NEED_MORE_INFO 반환
        if state.get("is_collecting_info", False):
            state["context_intent"] = "정보 수집 중"
            state["retrieved_documents"] = []
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True
            state["triage_decision"] = TriageDecisionType.NEED_MORE_INFO
            state["requires_consultant"] = False
            state["intent"] = IntentType.INFO_REQ
            logger.info(f"정보 수집 단계 감지 - Tool 사용 건너뛰기: 세션={state.get('session_id', 'unknown')}")
            return state
        
        # Tool을 직접 호출 (LLM을 거치지 않고)
        context_intent = intent_classification_tool.invoke({"user_message": user_message})
        rag_result_json = rag_search_tool.invoke({"query": user_message, "top_k": 5})
        retrieved_docs = parse_rag_result(rag_result_json)
        
        # 대화 이력 Tool 호출 (조건부: 대화 이력이 있을 때만)
        conversation_history = state.get("conversation_history", [])
        if conversation_history:
            formatted_history = chat_history_tool.invoke({
                "conversation_history": conversation_history,
                "max_messages": 10,  # 최근 10개 메시지만 (토큰 제한 고려)
                "include_timestamps": False  # 타임스탬프는 불필요
            })
            logger.info(f"대화 이력 로드 - 세션={state.get('session_id', 'unknown')}, 메시지 수={len(conversation_history)}")
        else:
            formatted_history = "대화 이력이 없습니다. (첫 대화입니다)"
            logger.debug(f"대화 이력 없음 - 첫 대화: 세션={state.get('session_id', 'unknown')}")
        
        # 상태 업데이트
        state["context_intent"] = context_intent
        state["retrieved_documents"] = retrieved_docs
        if retrieved_docs:
            state["rag_best_score"] = max(doc["score"] for doc in retrieved_docs)
            state["rag_low_confidence"] = state["rag_best_score"] < 0.2
        else:
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True
        
        # TODO: 여기에 새로운 프롬프트와 결정 로직을 추가하세요
        
    except Exception as e:
        # 에러 발생 시 기본값 (챗봇으로 처리)
        error_msg = str(e)
        logger.error(f"판단 에이전트 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
        
        # 연결 오류인 경우 특별 처리
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            logger.error(f"LM Studio 연결 오류 - 세션: {state.get('session_id', 'unknown')}, LM Studio가 실행 중인지 확인하세요")
        
        state["triage_decision"] = TriageDecisionType.AUTO_HANDLE_OK  # 에러 시 기본값
        state["requires_consultant"] = False
        state["handover_reason"] = None
        state["intent"] = IntentType.INFO_REQ  # 기본값
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["decision_error"] = error_msg
    
    return state

