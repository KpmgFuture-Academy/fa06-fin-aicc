# ai_engine/graph/nodes/answer_agent.py

"""챗봇 답변 생성 에이전트: GPT 모델 호출."""

from __future__ import annotations
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from app.schemas.chat import SourceDocument
from app.core.config import settings
from app.schemas.common import TriageDecisionType
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


# ============================================================================
# 프롬프트 생성 헬퍼 함수들
# ============================================================================

def _create_question_generation_prompt(user_message: str, context_intent: str, retrieved_docs: list) -> tuple[SystemMessage, HumanMessage]:
    """NEED_MORE_INFO 케이스: 추가 정보 요청 질문 생성 프롬프트"""
    system_message = SystemMessage(content="""당신은 고객에게 추가 정보를 요청하는 챗봇 어시스턴트입니다.
고객의 질문이 모호하거나 불완전한 경우, 답변을 위해 필요한 추가 정보를 정중하게 질문하세요.

질문 생성 시 주의사항:
- 한 번에 하나의 구체적인 질문만 하세요
- 예의바르고 친절한 톤을 유지하세요
- 고객이 쉽게 답변할 수 있는 질문으로 하세요
- 불필요한 정보를 요청하지 마세요""")
    
    # 검색된 문서가 있으면 참고하여 질문 생성
    context = ""
    if retrieved_docs:
        context = "\n\n[참고 문서]\n" + "\n\n".join([
            f"[문서 {i+1}] {doc['content'][:300]}..." 
            for i, doc in enumerate(retrieved_docs[:2])
        ])
    
    human_message = HumanMessage(content=f"""고객의 질문을 분석하여 추가 정보가 필요한 경우, 정중하게 질문을 생성해주세요.

[고객 질문]
{user_message}
{context}

[문맥 의도]
{context_intent if context_intent else "알 수 없음"}

위 정보를 바탕으로 답변을 위해 필요한 추가 정보를 정중하게 질문해주세요.""")
    
    return system_message, human_message


def _create_answer_generation_prompt(user_message: str, context_intent: str, retrieved_docs: list) -> tuple[SystemMessage, HumanMessage]:
    """AUTO_HANDLE_OK 케이스: RAG 문서 기반 답변 생성 프롬프트"""
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
    
    return system_message, human_message


# ============================================================================
# 메인 노드 함수
# ============================================================================

def answer_agent_node(state: GraphState) -> GraphState:
    """프롬프트를 구성해 LLM에게 답변 생성을 요청하고 상태를 갱신한다.
    
    triage_decision 값에 따라 다른 방식으로 처리:
    - AUTO_HANDLE_OK: RAG 문서 기반 답변 생성
    - NEED_MORE_INFO: 추가 정보를 위한 질문 생성
    - HUMAN_REQUIRED: 상담사 연결 안내 메시지
    """
    user_message = state["user_message"]
    triage_decision = state.get("triage_decision")
    context_intent = state.get("context_intent")  # triage_agent에서 설정된 문맥 의도
    retrieved_docs = state.get("retrieved_documents", [])
    
    # 상담사 연결 긍정/부정 응답 감지 (이전 턴에서 HUMAN_REQUIRED였고, 사용자가 응답한 경우)
    conversation_history = state.get("conversation_history", [])
    is_handover_confirmation = False
    is_handover_rejection = False
    if conversation_history:
        # 최근 메시지 확인 (상담사 연결 안내 후 사용자 응답)
        recent_messages = conversation_history[-2:] if len(conversation_history) >= 2 else conversation_history
        if any("상담사 연결하시겠습니까" in msg.get("message", "") for msg in recent_messages if msg.get("role") == "assistant"):
            # 사용자의 긍정/부정 응답 키워드 확인
            positive_keywords = ["예", "네", "연결", "좋아요", "좋아", "좋습니다", "연결해", "연결해주세요", "연결해줘", "연결요", "부탁", "부탁해", "부탁드려요"]
            negative_keywords = ["아니오", "아니요", "싫어", "싫어요", "싫습니다", "안 해", "안해", "안 할래", "안 할게", "안 할게요", "괜찮아", "괜찮아요", "필요 없어", "필요없어", "필요 없어요", "필요없어요", "안 해요", "안해요", "거절", "거절해", "거절할게", "안 할게요"]
            user_response = user_message.strip()
            is_handover_confirmation = any(keyword in user_response for keyword in positive_keywords)
            is_handover_rejection = any(keyword in user_response for keyword in negative_keywords)
    
    # ========================================================================
    # 분기 처리: triage_decision에 따라 다른 방식으로 처리
    # ========================================================================
    
    # ------------------------------------------------------------------------
    # 케이스 1: HUMAN_REQUIRED - 상담사 연결 안내
    # ------------------------------------------------------------------------
    if triage_decision == TriageDecisionType.HUMAN_REQUIRED:
        if is_handover_confirmation:
            # 사용자가 상담사 연결에 긍정 응답한 경우: 정보 수집 시작
            state["is_collecting_info"] = True
            state["info_collection_count"] = 0
            state["ai_message"] = "상담사 연결 전, 빠른 업무 처리를 도와드리기 위해 추가적인 질문을 드리겠습니다."
            logger.info(f"상담사 연결 긍정 응답 감지 - 정보 수집 시작: 세션={state.get('session_id', 'unknown')}")
            state["source_documents"] = []
            return state
        elif is_handover_rejection:
            # 사용자가 상담사 연결을 거절한 경우: 상담 종료
            state["ai_message"] = "상담사를 연결하지 않아 상담이 종료됩니다."
            logger.info(f"상담사 연결 부정 응답 감지 - 상담 종료: 세션={state.get('session_id', 'unknown')}")
            state["source_documents"] = []
            return state
        else:
            # 기본 안내 메시지 (첫 번째 상담사 연결 제안)
            state["ai_message"] = "상담사가 필요한 업무입니다. 상담사 연결하시겠습니까?"
            logger.info(f"HUMAN_REQUIRED 처리 - 상담사 연결 안내: 세션={state.get('session_id', 'unknown')}")
            state["source_documents"] = []
            return state
    
    # ------------------------------------------------------------------------
    # 케이스 2: NEED_MORE_INFO - 추가 정보 요청 질문 생성
    # ------------------------------------------------------------------------
    elif triage_decision == TriageDecisionType.NEED_MORE_INFO:
        try:
            # 정보 수집 단계인지 확인
            is_collecting = state.get("is_collecting_info", False)
            current_count = state.get("info_collection_count", 0)
            
            # 정보 수집 6번째 턴 (count가 5에서 6으로 증가한 후)
            if is_collecting and current_count >= 6:
                # 질문 생성 대신 고정 메시지 출력
                state["ai_message"] = "상담사 연결 예정입니다. 잠시만 기다려주세요."
                state["source_documents"] = []
                logger.info(f"정보 수집 완료 - 상담사 연결 안내 메시지 출력: 세션={state.get('session_id', 'unknown')}, 횟수: {current_count}")
                return state
            
            # 1~5번째 질문 생성 (기존 로직)
            # 프롬프트 생성 (헬퍼 함수 사용)
            system_message, human_message = _create_question_generation_prompt(
                user_message, context_intent, retrieved_docs
            )
            
            # LLM 호출하여 질문 생성
            logger.info(f"추가 정보 질문 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
            response = llm.invoke([system_message, human_message])
            question = response.content
            state["ai_message"] = question
            logger.info(f"추가 정보 질문 생성 완료 - 세션: {state.get('session_id', 'unknown')}, 질문 길이: {len(question)}")
            
            # 정보 수집 단계면 카운트 증가
            if is_collecting:
                state["info_collection_count"] = current_count + 1
                logger.info(f"정보 수집 질문 생성 - 세션: {state.get('session_id', 'unknown')}, 횟수: {state['info_collection_count']}/6 (1~5: 질문, 6: 연결 안내)")
            
            # source_documents 설정 (있는 경우)
            if retrieved_docs:
                source_docs = [
                    SourceDocument(
                        source=doc.get("source", "unknown"),
                        page=doc.get("page", 0),
                        score=doc.get("score", 0.0)
                    )
                    for doc in retrieved_docs
                ]
                state["source_documents"] = source_docs
            else:
                state["source_documents"] = []
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"추가 정보 질문 생성 중 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
            state["ai_message"] = "추가 정보가 필요합니다. 좀 더 구체적으로 질문해주시면 도와드리겠습니다."
            state["source_documents"] = []
            if "metadata" not in state:
                state["metadata"] = {}
            state["metadata"]["answer_error"] = error_msg
        
        return state
    
    # ------------------------------------------------------------------------
    # 케이스 3: AUTO_HANDLE_OK - RAG 문서 기반 답변 생성
    # ------------------------------------------------------------------------
    elif triage_decision == TriageDecisionType.AUTO_HANDLE_OK:
        # 문서 검증
        if not retrieved_docs:
            state["ai_message"] = "죄송합니다. 관련 문서를 찾을 수 없어 답변을 생성할 수 없습니다."
            state["source_documents"] = []
            if "metadata" not in state:
                state["metadata"] = {}
            state["metadata"]["answer_error"] = "retrieved_documents가 없습니다"
            return state
        
        try:
            # 프롬프트 생성 (헬퍼 함수 사용)
            system_message, human_message = _create_answer_generation_prompt(
                user_message, context_intent, retrieved_docs
            )

            # LLM 호출하여 답변 생성
            logger.info(f"답변 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
            response = llm.invoke([system_message, human_message])
            answer = response.content
            state["ai_message"] = answer
            logger.info(f"답변 생성 완료 - 세션: {state.get('session_id', 'unknown')}, 답변 길이: {len(answer)}")
            
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
        
        except Exception as e:
            # 에러 처리
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
    
    # ------------------------------------------------------------------------
    # 케이스 4: Fallback - triage_decision이 없거나 예상치 못한 값
    # ------------------------------------------------------------------------
    else:
        logger.warning(f"triage_decision이 없거나 예상치 못한 값: {triage_decision}, 기본 처리: 세션={state.get('session_id', 'unknown')}")
        
        if retrieved_docs:
            # 문서가 있으면 기본 로직으로 답변 생성 시도
            try:
                system_message, human_message = _create_answer_generation_prompt(
                    user_message, context_intent, retrieved_docs
                )
                response = llm.invoke([system_message, human_message])
                state["ai_message"] = response.content
                state["source_documents"] = [
                    SourceDocument(
                        source=doc.get("source", "unknown"),
                        page=doc.get("page", 0),
                        score=doc.get("score", 0.0)
                    )
                    for doc in retrieved_docs
                ]
            except Exception as e:
                state["ai_message"] = "죄송합니다. 답변 생성 중 오류가 발생했습니다."
                state["source_documents"] = []
        else:
            state["ai_message"] = "죄송합니다. 관련 문서를 찾을 수 없어 답변을 생성할 수 없습니다."
            state["source_documents"] = []
    
    return state