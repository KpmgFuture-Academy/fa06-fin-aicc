# ai_engine/graph/nodes/decision_agent.py

from __future__ import annotations
import logging

from langchain_openai import ChatOpenAI
from ai_engine.graph.state import GraphState
from app.core.config import settings

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


def decision_agent_node(state: GraphState) -> GraphState:
    """고객 질문을 판단하여 상담사 연결 필요 여부를 결정하는 노드."""
    user_message = state["user_message"]
    intent = state.get("intent")
    
    # LLM에게 판단 요청
    prompt = f"""다음 고객 질문을 분석하여 상담사 연결이 필요한지 판단해주세요.

[고객 질문]
{user_message}

[의도 분류 결과]
{intent.value if intent else "분류 중"}

다음 중 하나로만 답변해주세요:
- "상담사 연결 필요" (복잡한 민원, 계약 변경, 상담사 직접 요청 등)
- "챗봇으로 처리 가능" (단순 정보 문의, FAQ 질문 등)

답변:"""
    
    try:
        logger.info(f"판단 에이전트 실행 - 세션: {state.get('session_id', 'unknown')}")
        response = llm.invoke(prompt).content
        logger.debug(f"판단 에이전트 응답 - 세션: {state.get('session_id', 'unknown')}, 응답: {response[:100]}")
        
        # LLM 응답을 파싱하여 판단
        if "상담사 연결 필요" in response or "상담사" in response:
            state["requires_consultant"] = True
            state["handover_reason"] = response.strip()
            logger.info(f"상담사 연결 필요로 판단 - 세션: {state.get('session_id', 'unknown')}")
        else:
            state["requires_consultant"] = False
            state["handover_reason"] = None
            logger.info(f"챗봇으로 처리 가능으로 판단 - 세션: {state.get('session_id', 'unknown')}")
            
    except Exception as e:
        # 에러 발생 시 기본값 (챗봇으로 처리)
        error_msg = str(e)
        logger.error(f"판단 에이전트 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
        
        # 연결 오류인 경우 특별 처리
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            logger.error(f"LM Studio 연결 오류 - 세션: {state.get('session_id', 'unknown')}, LM Studio가 실행 중인지 확인하세요")
        
        state["requires_consultant"] = False
        state["handover_reason"] = None
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["decision_error"] = error_msg
    
    return state

