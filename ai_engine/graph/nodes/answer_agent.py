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


def _handle_error(error_msg: str, state: GraphState) -> None:
    """공통 에러 처리"""
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
        state["ai_message"] = "죄송합니다. 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        logger.error(f"답변 생성 기타 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}")
    
    if "metadata" not in state:
        state["metadata"] = {}
    state["metadata"]["answer_error"] = error_msg


def answer_agent_node(state: GraphState) -> GraphState:
    """프롬프트를 구성해 LLM에게 답변 생성을 요청하고 상태를 갱신한다.
    
    triage_decision 값에 따라 다른 프롬프트를 사용하여 처리:
    - SIMPLE_ANSWER: 간단한 자연어 답변 생성
    - AUTO_ANSWER: RAG 문서 기반 답변 생성
    - NEED_MORE_INFO: 추가 정보 요청 질문 생성
    - HUMAN_REQUIRED: 상담사 연결 안내 메시지 생성
    """
    user_message = state["user_message"]
    triage_decision = state.get("triage_decision")
    retrieved_docs = state.get("retrieved_documents", [])
    customer_intent_summary = state.get("customer_intent_summary")
    
    # ========================================================================
    # 티켓별 프롬프트 생성 및 LLM 호출
    # ========================================================================
    try:
        # ------------------------------------------------------------------------
        # 티켓 1: SIMPLE_ANSWER - 간단한 자연어 답변 생성
        # 사용 정보: user_message, customer_intent_summary
        # RAG 검색 결과: 사용 안 함
        # ------------------------------------------------------------------------
        if triage_decision == TriageDecisionType.SIMPLE_ANSWER:
            # customer_intent_summary 정보 포함
            intent_summary_hint = f"\n[고객 의도 요약: {customer_intent_summary}]" if customer_intent_summary else ""
            
            system_message = SystemMessage(content="""당신은 카드사 고객센터의 챗봇 어시스턴트입니다.
간단하고 자연스러운 응답만 생성하세요.

중요: 당신은 카드/금융 관련 상담만 제공합니다. 다른 주제는 정중히 거절하세요.

응답 규칙:
1) 단순 확인/동의/짧은 반응인 경우
   - 예: "네", "넵", "맞아요", "그거요", "알겠어요", "계속 해주세요"
   - → 이전 답변을 인정/확인하는 짧은 응답만 생성
   - 예: "네, 알겠습니다. 계속 진행하겠습니다."

2) 감사 인사/끝맺음인 경우
   - 예: "감사합니다", "덕분에 해결됐어요", "수고하세요", "고마워요"
   - → 간단한 인사로 대답
   - 예: "도움이 되어서 다행입니다. 추가 요청사항이 있으신가요?"

3) 시스템/잡음/의미 없는 입력인 경우
   - 예: "", "…", "음", "아아", "ㅋㅋㅋ", "ㅎㅎㅎ", STT 오류로 보이는 텍스트
   - → 재입력을 요청하는 간단한 문장만 생성
   - 예: "죄송하지만, 무엇을 도와드릴까요? 카드 관련 문의사항이 있으시면 말씀해 주세요."

4) 카드/금융과 무관한 질문인 경우 (중요!)
   - 예: "피자 주문", "날씨", "주식 투자", "맛집 추천", "영화 추천" 등
   - → 정중히 거절하고 카드 관련 문의를 안내
   - 예: "죄송합니다. 저는 카드 및 금융 관련 상담만 도와드릴 수 있습니다. 카드 이용, 결제, 한도, 분실 신고 등에 대해 문의해 주세요."

5) 욕설/비속어/부적절한 표현인 경우
   - → 정중하게 대화 예절을 요청
   - 예: "원활한 상담을 위해 정중한 표현을 부탁드립니다. 카드 관련 문의사항이 있으시면 말씀해 주세요."

6) 영어 또는 외국어 입력인 경우
   - → 한국어 사용을 요청
   - 예: "죄송합니다. 현재 한국어 상담만 지원하고 있습니다. 한국어로 다시 말씀해 주시겠어요?"

7) 직전 턴에 이미 충분히 답변이 끝난 경우
   - 추가 질문이 전혀 없는 단순 리액션
   - → 대화를 마무리하거나 짧게 응답
   - 예: "추가 질문이 없으시면, 언제든 다시 문의해 주세요.""")
            
            human_message = HumanMessage(content=f"""간단하고 자연스러운 응답을 생성해주세요.

[고객 메시지]
{user_message}
{intent_summary_hint}""")
            
            logger.info(f"SIMPLE_ANSWER 답변 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
            response = llm.invoke([system_message, human_message])
            state["ai_message"] = response.content
            state["source_documents"] = []
            logger.info(f"SIMPLE_ANSWER 답변 생성 완료 - 세션: {state.get('session_id', 'unknown')}")
        
        # ------------------------------------------------------------------------
        # 티켓 2: AUTO_ANSWER - RAG 문서 기반 답변 생성
        # 사용 정보: user_message, customer_intent_summary, retrieved_docs
        # RAG 검색 결과: 사용 (필수)
        # ------------------------------------------------------------------------
        elif triage_decision == TriageDecisionType.AUTO_ANSWER:
            if not retrieved_docs:
                state["ai_message"] = "죄송합니다. 해당 업무는 상담원에게 문의해주세요."
                state["source_documents"] = []
                return state
            
            # customer_intent_summary 정보 포함
            intent_summary_hint = f"\n[고객 의도 요약: {customer_intent_summary}]" if customer_intent_summary else ""
            
            # 검색된 문서를 프롬프트에 포함
            context = "\n\n".join([
                f"[문서 {i+1}] {doc['content']} (출처: {doc['source']}, 페이지: {doc['page']}, 유사도: {doc['score']:.2f})"
                for i, doc in enumerate(retrieved_docs)
            ])
            
            system_message = SystemMessage(content="""당신은 고객 질문에 답변하는 챗봇 어시스턴트입니다.
제공된 참고 문서를 기반으로 정확하고 예의바른 답변을 생성하세요.
근거 문서에 없는 내용은 추측하지 말고, 정확한 정보만 제공하세요.""")
            
            human_message = HumanMessage(content=f"""참고 문서를 기반으로 고객 질문에 대한 답변을 생성해주세요.

[참고 문서]
{context}
{intent_summary_hint}

[고객 질문]
{user_message}""")
            
            logger.info(f"AUTO_ANSWER 답변 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
            response = llm.invoke([system_message, human_message])
            state["ai_message"] = response.content
            
            # retrieved_documents를 source_documents로 변환
            state["source_documents"] = [
                SourceDocument(
                    source=doc.get("source", "unknown"),
                    page=doc.get("page", 0),
                    score=doc.get("score", 0.0)
                )
                for doc in retrieved_docs
            ]
            logger.info(f"AUTO_ANSWER 답변 생성 완료 - 세션: {state.get('session_id', 'unknown')}")
        
        # ------------------------------------------------------------------------
        # 티켓 3: NEED_MORE_INFO - 추가 정보 요청 질문 생성
        # 사용 정보: user_message, customer_intent_summary
        # RAG 검색 결과: 사용 안 함
        # ------------------------------------------------------------------------
        elif triage_decision == TriageDecisionType.NEED_MORE_INFO:
            # customer_intent_summary 정보 포함
            intent_summary_hint = f"\n[고객 의도 요약: {customer_intent_summary}]" if customer_intent_summary else ""
            
            system_message = SystemMessage(content="""당신은 고객에게 추가 정보를 요청하는 챗봇 어시스턴트입니다.
답변을 위해 필요한 추가 정보를 정중하게 질문하세요.

질문 생성 시 주의사항:
- 한 번에 하나의 구체적인 질문만 하세요
- 예의바르고 친절한 톤을 유지하세요
- 고객이 쉽게 답변할 수 있는 질문으로 하세요
- 불필요한 정보를 요청하지 마세요""")
            
            human_message = HumanMessage(content=f"""답변을 위해 필요한 추가 정보를 정중하게 질문해주세요.

[고객 질문]
{user_message}
{intent_summary_hint}""")
            
            logger.info(f"NEED_MORE_INFO 질문 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
            response = llm.invoke([system_message, human_message])
            state["ai_message"] = response.content
            state["source_documents"] = []
            logger.info(f"NEED_MORE_INFO 질문 생성 완료 - 세션: {state.get('session_id', 'unknown')}")
        
        # ------------------------------------------------------------------------
        # 티켓 4: HUMAN_REQUIRED - 상담사 연결 안내 메시지 생성
        # 사용 정보: user_message, customer_intent_summary
        # RAG 검색 결과: 사용 안 함
        # ------------------------------------------------------------------------
        elif triage_decision == TriageDecisionType.HUMAN_REQUIRED:
            # customer_intent_summary 정보 포함
            intent_summary_hint = f"\n[고객 의도 요약: {customer_intent_summary}]" if customer_intent_summary else ""
            
            system_message = SystemMessage(content="""당신은 상담사 연결을 안내하는 챗봇 어시스턴트입니다.
상담사가 이어받을 수 있도록 정중하고 공감 어린 어조로 안내 문장을 생성하세요.

안내 메시지 규칙:
- "상담사에게 연결해 드리겠다"는 내용을 포함
- 정중하고 공감 어린 어조 사용
- 예시:
  - "정확한 확인을 위해 상담사에게 연결해 드리겠습니다."
  - "불편을 겪으셔서 죄송합니다. 자세한 확인을 위해 담당 상담사가 이어서 도와드리겠습니다."
  - "복잡한 사안이므로 전문 상담사에게 연결해 드리겠습니다."

중요: 추가 정보 요청이나 문제 해결 시도 없이, 상담사 연결 안내만 생성하세요.""")
            
            human_message = HumanMessage(content=f"""정중하고 공감 어린 상담사 연결 안내 메시지를 생성해주세요.

[고객 메시지]
{user_message}
{intent_summary_hint}""")
            
            logger.info(f"HUMAN_REQUIRED 안내 메시지 생성 시작 - 세션: {state.get('session_id', 'unknown')}")
            response = llm.invoke([system_message, human_message])
            # 상담사 연결 안내 메시지 뒤에 고정 메시지 추가
            fixed_message = "\n\n고객님의 문의를 빠르게 해결해드리기 위해 상담사 연결 전까지 정보를 수집할 예정입니다. 상담사 연결을 원하시면 '네'라고 말씀해주세요. 상담사 연결을 원하지 않으시면 '아니오'라고 말씀해주세요."
            state["ai_message"] = response.content + fixed_message
            state["source_documents"] = []
            
            # HUMAN_REQUIRED 플로우 진입 플래그 설정
            state["is_human_required_flow"] = True
            state["customer_consent_received"] = False
            state["collected_info"] = {}
            state["info_collection_complete"] = False
            logger.info(f"HUMAN_REQUIRED 안내 메시지 생성 완료 - 세션: {state.get('session_id', 'unknown')}, HUMAN_REQUIRED 플로우 진입")
        
        # ------------------------------------------------------------------------
        # Fallback: triage_decision이 없거나 예상치 못한 값
        # 문서가 있으면 AUTO_ANSWER 로직, 없으면 SIMPLE_ANSWER 로직 사용
        # ------------------------------------------------------------------------
        else:
            logger.warning(f"triage_decision이 없거나 예상치 못한 값: {triage_decision}, 기본 처리: 세션={state.get('session_id', 'unknown')}")
            if retrieved_docs:
                # AUTO_ANSWER 로직 사용
                intent_summary_hint = f"\n[고객 의도 요약: {customer_intent_summary}]" if customer_intent_summary else ""
                context = "\n\n".join([
                    f"[문서 {i+1}] {doc['content']} (출처: {doc['source']}, 페이지: {doc['page']}, 유사도: {doc['score']:.2f})"
                    for i, doc in enumerate(retrieved_docs)
                ])
                
                system_message = SystemMessage(content="""당신은 고객 질문에 답변하는 챗봇 어시스턴트입니다.
제공된 참고 문서를 기반으로 정확하고 예의바른 답변을 생성하세요.
근거 문서에 없는 내용은 추측하지 말고, 정확한 정보만 제공하세요.""")
                
                human_message = HumanMessage(content=f"""참고 문서를 기반으로 고객 질문에 대한 답변을 생성해주세요.

[참고 문서]
{context}
{intent_summary_hint}

[고객 질문]
{user_message}""")
                
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
            else:
                # SIMPLE_ANSWER 로직 사용 (Fallback)
                intent_summary_hint = f"\n[고객 의도 요약: {customer_intent_summary}]" if customer_intent_summary else ""

                system_message = SystemMessage(content="""당신은 카드사 고객센터의 챗봇 어시스턴트입니다.
간단하고 자연스러운 응답만 생성하세요.

중요: 당신은 카드/금융 관련 상담만 제공합니다. 다른 주제는 정중히 거절하세요.

응답 규칙:
1) 카드/금융과 무관한 질문인 경우
   - → "죄송합니다. 저는 카드 및 금융 관련 상담만 도와드릴 수 있습니다. 카드 이용, 결제, 한도, 분실 신고 등에 대해 문의해 주세요."

2) 의미 없는 입력/잡음인 경우
   - → "무엇을 도와드릴까요? 카드 관련 문의사항이 있으시면 말씀해 주세요."

3) 욕설/비속어인 경우
   - → "원활한 상담을 위해 정중한 표현을 부탁드립니다."

4) 영어/외국어인 경우
   - → "죄송합니다. 현재 한국어 상담만 지원하고 있습니다." """)

                human_message = HumanMessage(content=f"""간단하고 자연스러운 응답을 생성해주세요.

[고객 메시지]
{user_message}
{intent_summary_hint}""")

                response = llm.invoke([system_message, human_message])
                state["ai_message"] = response.content
                state["source_documents"] = []
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"답변 생성 중 오류 발생 - 세션: {state.get('session_id', 'unknown')}, 티켓: {triage_decision}, 오류: {error_msg}", exc_info=True)
        _handle_error(error_msg, state)
        state["source_documents"] = []
    
    return state