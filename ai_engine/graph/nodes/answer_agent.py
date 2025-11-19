# ai_engine/graph/nodes/answer_agent.py

"""챗봇 답변 생성 에이전트: GPT 모델 호출."""

from __future__ import annotations
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from app.schemas.chat import SourceDocument
from app.core.config import settings
from ai_engine.prompts.templates import SYSTEM_PROMPT

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

def answer_agent_node(state: GraphState) -> GraphState:
    """프롬프트를 구성해 LLM에게 답변 생성을 요청하고 상태를 갱신한다.
    
    decision_agent에서 이미 검색한 retrieved_documents를 기반으로 답변을 생성합니다.
    retrieved_documents가 없으면 이미 decision_agent가 상담사 이관을 했을 것이므로
    이 노드가 실행되지 않습니다.
    """
    user_message = state["user_message"]
    context_intent = state.get("context_intent")  # decision_agent에서 설정된 문맥 의도
    
    # decision_agent에서 이미 검색한 결과 사용 (없으면 에러)
    retrieved_docs = state.get("retrieved_documents", [])
    
    if not retrieved_docs:
        # 문서가 없으면 이미 decision_agent가 상담사 이관했을 것
        # 이 경우는 answer_agent가 실행되지 않아야 하지만, 안전장치로 처리
        state["ai_message"] = "죄송합니다. 관련 문서를 찾을 수 없어 답변을 생성할 수 없습니다."
        state["source_documents"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["answer_error"] = "retrieved_documents가 없습니다"
        return state
    
    try:
        # System 메시지 설정
        system_message = SystemMessage(content=f"""{SYSTEM_PROMPT}

당신은 고객 질문에 답변하는 챗봇 어시스턴트입니다.
제공된 참고 문서를 기반으로 정확하고 예의바른 답변을 제공하세요.""")
        
        # context_intent 정보를 포함한 프롬프트 구성
        intent_hint = f"\n[문맥 의도: {context_intent}]" if context_intent else ""
        
        # 검색된 문서를 프롬프트에 포함
        context = "\n\n".join([
            f"[문서 {i+1}] {doc['content']} (출처: {doc['source']}, 페이지: {doc['page']}, 유사도: {doc['score']:.2f})"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        human_message = HumanMessage(content=f"""다음 문서를 참고하여 고객의 질문에 답변해주세요.

[참고 문서]
{context}
{intent_hint}

[고객 질문]
{user_message}

위 문서를 기반으로 답변해주세요.""")

        # LLM 호출 (origin 방식 + HEAD의 상세 로깅/에러 처리)
        logger.info(f"답변 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
        response = llm.invoke([system_message, human_message])
        answer = response.content
        state["ai_message"] = answer
        logger.info(f"답변 생성 완료 - 세션: {state.get('session_id', 'unknown')}, 답변 길이: {len(answer)}")
        
        # retrieved_documents를 source_documents로 변환 (try 블록 안에)
        source_docs = [
            SourceDocument(
                source=doc.get("source", "unknown"),
                page=doc.get("page", 0),
                score=doc.get("score", 0.0)
            )
            for doc in retrieved_docs
        ]
        state["source_documents"] = source_docs
        
    except Exception as e:
        # HEAD 버전의 상세한 에러 처리
        error_msg = str(e)
        logger.error(f"답변 생성 중 오류 발생 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
        
        if "quota" in error_msg.lower() or "429" in error_msg:
            state["ai_message"] = "죄송합니다. 현재 서비스 사용량이 초과되어 일시적으로 답변을 생성할 수 없습니다. 잠시 후 다시 시도해주세요."
            logger.warning(f"API 할당량 초과 - 세션: {state.get('session_id', 'unknown')}")
        elif "api_key" in error_msg.lower() or "401" in error_msg:
            state["ai_message"] = "죄송합니다. API 설정 오류가 발생했습니다. 관리자에게 문의해주세요."
            logger.error(f"API 키 오류 - 세션: {state.get('session_id', 'unknown')}")
        elif "connection" in error_msg.lower() or "refused" in error_msg.lower():
            state["ai_message"] = "죄송합니다. LM Studio 서버에 연결할 수 없습니다. LM Studio가 실행 중인지 확인해주세요."
            logger.error(f"LM Studio 연결 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}")
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            state["ai_message"] = "죄송합니다. 응답 생성에 시간이 오래 걸려 타임아웃이 발생했습니다. 더 간단한 질문으로 다시 시도해주세요."
            logger.warning(f"답변 생성 타임아웃 - 세션: {state.get('session_id', 'unknown')}, 타임아웃: {settings.llm_timeout}초")
        else:
            state["ai_message"] = f"죄송합니다. 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            logger.error(f"답변 생성 기타 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}")
        
        # 에러 정보 저장
        state["source_documents"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["answer_error"] = error_msg
    
    return state