# ai_engine/graph/nodes/decision_agent.py

from __future__ import annotations
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from app.core.config import settings
from ai_engine.graph.tools import intent_classification_tool, rag_search_tool
from ai_engine.graph.tools.rag_search_tool import parse_rag_result
from app.schemas.common import IntentType

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
    """고객 질문을 판단하여 상담사 연결 필요 여부를 결정하는 노드.
    
    intent_classification_tool과 rag_search_tool을 직접 호출하여 
    의도 분류와 RAG 검색 결과를 얻은 후, 그 결과를 기반으로 상담사 이관 필요 여부를 결정합니다.
    """
    user_message = state["user_message"]
    
    try:
        # 1단계: 직접적인 상담원 연결 요청 감지 (RAG 검색 전에 먼저 체크)
        direct_handover_keywords = [
            "상담원 연결", "상담사 연결", "상담원 연결해", "상담사 연결해",
            "상담원 연결해줘", "상담사 연결해줘", "상담원 연결해주세요", "상담사 연결해주세요",
            "상담원 연결요", "상담사 연결요", "상담원 연결 부탁", "상담사 연결 부탁",
            "직원 연결", "직원 연결해", "직원 연결해줘", "직원 연결해주세요",
            "상담원과 통화", "상담사와 통화", "직원과 통화", "상담원과 대화", "상담사와 대화",
            "상담원 전화", "상담사 전화", "직원 전화", "상담원 부르", "상담사 부르",
            "상담원 필요", "상담사 필요", "직원 필요", "상담원 원해", "상담사 원해",
            "상담원으로", "상담사로", "직원으로", "상담원한테", "상담사한테"
        ]
        
        # 키워드 매칭
        is_direct_handover_request = any(
            keyword in user_message for keyword in direct_handover_keywords
        )
        
        # 패턴 매칭 (더 포괄적인 감지)
        # "상담원/상담사/직원" + "연결/부르/필요/원해" 같은 패턴
        import re
        handover_patterns = [
            r"상담원.*연결", r"상담사.*연결", r"직원.*연결",
            r"상담원.*부르", r"상담사.*부르", r"직원.*부르",
            r"상담원.*필요", r"상담사.*필요", r"직원.*필요",
            r"상담원.*원해", r"상담사.*원해", r"직원.*원해",
            r"연결.*상담원", r"연결.*상담사", r"연결.*직원",
            r"부르.*상담원", r"부르.*상담사", r"부르.*직원"
        ]
        
        is_pattern_match = any(
            re.search(pattern, user_message, re.IGNORECASE) for pattern in handover_patterns
        )
        
        is_direct_handover_request = is_direct_handover_request or is_pattern_match
        
        # 직접적인 상담원 연결 요청이면 RAG 검색 없이 바로 상담원 이관
        if is_direct_handover_request:
            state["context_intent"] = "상담원 연결 요청"
            state["retrieved_documents"] = []
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True
            state["requires_consultant"] = True
            state["handover_reason"] = "고객이 직접 상담원 연결을 요청함"
            state["intent"] = IntentType.HUMAN_REQ
            logger.info(f"직접 상담원 연결 요청 감지 - 상담원 이관: 세션={state.get('session_id', 'unknown')}, 메시지='{user_message}'")
            return state
        
        # Tool을 직접 호출 (LLM을 거치지 않고)
        context_intent = intent_classification_tool.invoke({"user_message": user_message})
    
        rag_result_json = rag_search_tool.invoke({"query": user_message, "top_k": 5})
        retrieved_docs = parse_rag_result(rag_result_json)
        
        # 상태 업데이트
        state["context_intent"] = context_intent
        state["retrieved_documents"] = retrieved_docs
        if retrieved_docs:
            state["rag_best_score"] = max(doc["score"] for doc in retrieved_docs)
            # 유사도 임계값을 낮춤 (0.7 → 0.3): 검색 결과가 있으면 일단 챗봇으로 처리 시도
            state["rag_low_confidence"] = state["rag_best_score"] < 0.3
        else:
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True
        
        # Tool 결과를 기반으로 프롬프트 구성
        intent_info = f"문맥 의도 분류 결과: {context_intent}"
        rag_info = ""
        if retrieved_docs:
            rag_info = f"\n\n[검색된 문서] (최고 유사도: {state['rag_best_score']:.2f})\n"
            for i, doc in enumerate(retrieved_docs[:3], 1):  # 상위 3개만 표시
                rag_info += f"{i}. {doc['source']} (p.{doc['page']}, 유사도: {doc['score']:.2f})\n"
                rag_info += f"   내용: {doc['content'][:100]}...\n"
        else:
            rag_info = "\n\n[검색된 문서] 없음 (관련 문서를 찾지 못했습니다)"
        
        # System 메시지로 역할 정의
        system_message = SystemMessage(content="""당신은 고객 질문을 분석하여 상담사 연결이 필요한지 판단하는 에이전트입니다.

문맥 의도는 질문의 주제를 나타냅니다 (예: "대출", "예금", "카드론" 등).
이를 기반으로 상담사 연결 필요 여부를 판단하세요.

다음 기준에 따라 판단하세요:

상담사 연결이 필요한 경우 (다음 조건을 모두 만족해야 함):
- 고객이 상담사를 직접 요청한 경우 (예: "상담사 연결해줘", "직원과 통화하고 싶어요")
- 고객 메시지에 명확한 불만이나 민원 표현이 있는 경우 (예: "불만", "민원", "화가 났어요")
- RAG 검색 결과가 전혀 없는 경우 (검색된 문서가 0개)
- 복잡한 계약 변경이나 대출 신청 같은 경우

챗봇으로 처리 가능한 경우 (다음 중 하나라도 해당하면):
- 단순 정보 문의인 경우 (예: "카드론 한도가 얼마야?", "대출 금리는?", "예금 이자는?")
- RAG 검색 결과가 있는 경우 (검색된 문서가 1개 이상이면 챗봇으로 처리)
- FAQ 형태의 질문인 경우
- 문맥 의도가 "카드론", "대출", "예금", "신용카드" 같은 금융 상품 관련 정보 문의인 경우

중요: RAG 검색 결과가 있으면 (검색된 문서가 1개 이상) 반드시 챗봇으로 처리하세요.
단순 정보 문의는 상담사 연결이 필요하지 않습니다.

다음 형식으로만 답변해주세요:
- "상담사 연결 필요: [이유] | IntentType: HUMAN_REQ" 또는 "상담사 연결 필요: [이유] | IntentType: COMPLAINT"
- "챗봇으로 처리 가능: [이유] | IntentType: INFO_REQ"

IntentType 설명:
- HUMAN_REQ: 고객이 상담사를 직접 요청한 경우
- COMPLAINT: 고객의 불만이나 민원이 있는 경우
- INFO_REQ: 단순 정보 문의로 챗봇으로 처리 가능한 경우
""")
        
        human_message = HumanMessage(content=f"""다음 고객 질문을 분석해주세요:

[고객 질문]
{user_message}

{intent_info}
{rag_info}

이를 바탕으로 상담사 연결 필요 여부를 판단해주세요.""")
        
        # 개인화된 질문 감지 (유사도와 관계없이 상담원 이관 필요)
        personalization_keywords = [
            "내 경우", "나한테", "제 상황", "내 상황", "나에게", "제 경우",
            "내 것", "나의", "제 것", "개인적으로", "저는", "저에게",
            "내가", "제가", "나를", "저를", "내 정보", "제 정보",
            "내 계좌", "제 계좌", "내 대출", "제 대출", "내 보험", "제 보험",
            "나에게 해당", "저에게 해당", "내게 해당", "제게 해당",
            "나한테 적용", "저한테 적용", "내게 적용", "제게 적용",
            "내 거", "제 거", "나의 것", "저의 것"
        ]
        
        is_personalized_query = any(
            keyword in user_message for keyword in personalization_keywords
        )
        
        # 유사도 임계값 설정 (이 값보다 낮으면 상담원 이관)
        SIMILARITY_THRESHOLD = settings.similarity_threshold  # 설정에서 가져옴 (기본값: 0.5)
        
        # RAG 검색 결과와 유사도 점수 확인
        if retrieved_docs and len(retrieved_docs) > 0:
            best_score = state.get("rag_best_score", 0.0)
            
            # 개인화된 질문이면 유사도와 관계없이 상담원 이관
            if is_personalized_query:
                requires_consultant = True
                final_response = f"상담사 연결 필요: 개인화된 질문으로 개인 정보 확인이 필요함 (유사도: {best_score:.4f}) | IntentType: HUMAN_REQ"
                logger.warning(f"개인화된 질문 감지 - 상담원 이관: 세션={state.get('session_id', 'unknown')}, 검색 결과 수={len(retrieved_docs)}, 최고 유사도={best_score:.4f}")
            # 유사도가 임계값 이상이면 챗봇으로 처리
            elif best_score >= SIMILARITY_THRESHOLD:
                requires_consultant = False
                final_response = f"챗봇으로 처리 가능: RAG 검색 결과가 있고 유사도가 충분함 (유사도: {best_score:.4f}) | IntentType: INFO_REQ"
                logger.info(f"RAG 검색 결과 있음 - 챗봇으로 처리: 세션={state.get('session_id', 'unknown')}, 검색 결과 수={len(retrieved_docs)}, 최고 유사도={best_score:.4f} (임계값: {SIMILARITY_THRESHOLD})")
            else:
                # 유사도가 낮으면 상담원 이관
                requires_consultant = True
                final_response = f"상담사 연결 필요: RAG 검색 결과는 있으나 유사도가 낮아 정확한 답변을 제공하기 어려움 (유사도: {best_score:.4f}, 임계값: {SIMILARITY_THRESHOLD}) | IntentType: HUMAN_REQ"
                logger.warning(f"RAG 검색 결과 있으나 유사도 낮음 - 상담원 이관: 세션={state.get('session_id', 'unknown')}, 검색 결과 수={len(retrieved_docs)}, 최고 유사도={best_score:.4f} (임계값: {SIMILARITY_THRESHOLD})")
        else:
            # 검색 결과가 없으면 LLM으로 판단
            response = llm.invoke([system_message, human_message])
            final_response = response.content
            
            # 최종 판단: 상담사 연결 필요 여부 파싱
            requires_consultant = "상담사 연결 필요" in final_response
            logger.info(f"LLM 판단 결과: 세션={state.get('session_id', 'unknown')}, requires_consultant={requires_consultant}, 응답={final_response[:100]}")
        
        # IntentType 파싱 (LLM 응답에서 추출 시도)
        intent_type = None
        if "IntentType: HUMAN_REQ" in final_response or "| IntentType: HUMAN_REQ" in final_response:
            intent_type = IntentType.HUMAN_REQ
        elif "IntentType: COMPLAINT" in final_response or "| IntentType: COMPLAINT" in final_response:
            intent_type = IntentType.COMPLAINT
        elif "IntentType: INFO_REQ" in final_response or "| IntentType: INFO_REQ" in final_response:
            intent_type = IntentType.INFO_REQ
        
        # IntentType 파싱 실패 시 fallback 로직
        if intent_type is None:
            if requires_consultant:
                # 상담사 연결이 필요한 경우
                if "상담" in context_intent or any(keyword in user_message.lower() for keyword in ["상담사", "직원", "상담원", "연결"]):
                    intent_type = IntentType.HUMAN_REQ
                elif any(keyword in user_message.lower() for keyword in ["불만", "불편", "화가", "문제", "민원"]):
                    intent_type = IntentType.COMPLAINT
                else:
                    intent_type = IntentType.HUMAN_REQ  # 기본값
            else:
                intent_type = IntentType.INFO_REQ  # 챗봇으로 처리 가능
        
        # 상태 업데이트
        state["requires_consultant"] = requires_consultant
        state["handover_reason"] = final_response.strip() if requires_consultant else None
        state["intent"] = intent_type
            
    except Exception as e:
        # 에러 발생 시 기본값 (챗봇으로 처리)
        error_msg = str(e)
        logger.error(f"판단 에이전트 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
        
        # 연결 오류인 경우 특별 처리
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            logger.error(f"LM Studio 연결 오류 - 세션: {state.get('session_id', 'unknown')}, LM Studio가 실행 중인지 확인하세요")
        
        state["requires_consultant"] = False
        state["handover_reason"] = None
        state["intent"] = IntentType.INFO_REQ  # 기본값
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["decision_error"] = error_msg
    
    return state

