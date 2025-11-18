# ai_engine/graph/nodes/answer_agent.py

"""챗봇 답변 생성 에이전트: GPT 모델 호출."""

from __future__ import annotations
import logging
from langchain_openai import ChatOpenAI
from ai_engine.graph.state import GraphState
from app.schemas.chat import SourceDocument
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

def answer_agent_node(state: GraphState) -> GraphState:
    """프롬프트를 구성해 LLM에게 답변 생성을 요청하고 상태를 갱신한다."""
    # RAG 검색 결과 가져오기
    retrieved_docs = state.get("retrieved_documents", [])
    user_message = state["user_message"]
    
    # RAG 검색 결과를 프롬프트에 포함
    if retrieved_docs:
        # 문서 내용을 프롬프트에 추가
        context = "\n\n".join([
            f"[문서 {i+1}] {doc['content']} (출처: {doc['source']}, 페이지: {doc['page']})"
            for i, doc in enumerate(retrieved_docs)
        ])
        prompt = f"""다음 문서를 참고하여 고객의 질문에 답변해주세요.

[참고 문서]
{context}

[고객 질문]
{user_message}

[답변]
"""
    else:
        # 검색 결과가 없으면 사용자 메시지만 전달
        prompt = user_message
    
    # LLM 호출
    try:
        logger.info(f"답변 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
        answer = llm.invoke(prompt).content
        state["ai_message"] = answer
        logger.info(f"답변 생성 완료 - 세션: {state.get('session_id', 'unknown')}, 답변 길이: {len(answer)}")
    except Exception as e:
        # OpenAI API 오류 처리
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
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["answer_error"] = error_msg
    
    # retrieved_documents를 source_documents로 변환
    source_docs = [
        SourceDocument(
            source=doc.get("source", "unknown"),
            page=doc.get("page", 0),
            score=doc.get("score", 0.0)
        )
        for doc in retrieved_docs
    ]
    state["source_documents"] = source_docs
    
    return state