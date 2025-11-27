# ai_engine/graph/nodes/triage_agent.py

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain.agents import create_agent
from ai_engine.graph.state import GraphState
from app.core.config import settings
from ai_engine.graph.tools import intent_classification_tool, rag_search_tool
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


# 도구 리스트
tools = [intent_classification_tool, rag_search_tool]

SYSTEM_PROMPT = """
당신은 카드/금융 콜센터용 triage 에이전트입니다.
매 턴마다 고객의 최신 발화(user_message)와 대화 맥락, 도구 결과를 보고
아래 네 가지 티켓 중 하나를 JSON 형식으로 생성해야 합니다. 

- SIMPLE_ANSWER
- AUTO_ANSWER
- NEED_MORE_INFO
- HUMAN_REQUIRED

규칙 요약:

1) 입력 정보
- user_message: 방금 들어온 고객 발화 (메시지 히스토리의 마지막 HumanMessage)
- 대화 맥락: 이전 메시지 히스토리 (최대 10개, HumanMessage와 AIMessage로 구성)
- (선택) intent_classification_tool 결과: 상위 3개 문맥 의도와 confidence
- (선택) rag_search_tool 결과: 관련 문서 top3

2) 도구 사용 규칙
- intent_classification_tool, rag_search_tool: 필요한 경우에만 호출한다.
- 대화 맥락은 이미 메시지 히스토리로 제공되므로 별도 도구 호출 불필요.

3) 도구를 쓰지 말아야 하는 경우 (도구 호출 없이 판단)
- 단순 반응/동의/짧은 리액션
  예: "네", "넵", "맞아요", "계속 해주세요"
  → SIMPLE_ANSWER
- 감사/마무리 인사
  예: "감사합니다", "해결됐어요", "수고하세요"
  → SIMPLE_ANSWER
- 의미 없는 입력/STT 오류
  예: "", "...", "음"
  → SIMPLE_ANSWER (다시 한번 또렷하게 말씀해달라고 요청)
- 이미 해결된 뒤의 가벼운 리액션
  → SIMPLE_ANSWER

4) 상담사 이관이 필요한 경우
   상담사 연결(HUMAN_REQUIRED)은 아래 조건에 정확히 해당할 때만 선택하세요.
   - 이미 여러 차례 안내했으나 여전히 해결되지 않아 고객이 인내심을 잃고 있는 상황 (강한 불만/민원)
  → HUMAN_REQUIRED
이 경우에는 intent_classification_tool, rag_search_tool을 호출하지 말고,
상담사에게 이관해야 한다는 안내 문장을 생성한다.

5) 도구가 필요한 대표 상황 (AUTO_ANSWER 또는 NEED_MORE_INFO 후보)
- 새로운 정보/설명을 요구하는 명확한 질문
- 이전 주제와 다른 새로운 질문
- 약관/상품/정책/요금/절차 등 문서 기반 설명이 필요한 질문
- 답변을 위해 추가 정보(상품명, 날짜, 금액 등)가 필요한 질문

이 경우에는:
- 메시지 히스토리의 대화 맥락을 참고하고,
- 필요하다면 intent_classification_tool로 의도 분류,
- rag_search_tool로 문서 검색을 수행한다.
- 도구 결과만으로 충분히 답변 가능하면: AUTO_ANSWER
- 도구 결과를 봐도 고객 추가 정보가 필요하면: NEED_MORE_INFO
- 자동 응답이 부적절하거나 복잡 민원으로 판단되면: HUMAN_REQUIRED

6) 판단 기준
모든 판단은 다음을 모두 참고해야 한다.
- user_message (이번 턴 고객 발화 - 메시지 히스토리의 마지막 HumanMessage)
- 대화 맥락 (메시지 히스토리의 이전 HumanMessage와 AIMessage)
- (있다면) intent_classification_tool 결과 (JSON 문자열)
- (있다면) rag_search_tool 결과 (문서 리스트 등)
도구 호출 결과(ToolMessage)에 포함된 결과를 꼼꼼히 읽고 종합 판단한다.

단, HUMAN_REQUIRED를 선택할 때는 아래 두 질문을 참고해서 판단한다.
- “고객이 상담사 연결을 명시적으로 요청했는가?”
- “자동 응답으로 해결할 수 없음이 반복적으로 확인되었는가?”
두 질문 중 하나라도 “아니오”라면 HUMAN_REQUIRED를 선택하지 말고 다른 티켓을 고려한다.

7) 최종 출력 형식
도구 호출이 더 이상 필요 없다고 판단되면,
반드시 아래 JSON 형식 하나만 출력한다.

{
  "ticket": "AUTO_ANSWER",
  "reason": "약관 기반 RAG 검색 결과로 충분히 답변 가능",
  "customer_intent_summary": "고객의 핵심 의도를 1-2문장으로 요약"
}

- ticket: SIMPLE_ANSWER / AUTO_ANSWER / NEED_MORE_INFO / HUMAN_REQUIRED 중 하나
- reason: 내부 판단 근거를 간단히 설명
- customer_intent_summary: 고객의 핵심 의도를 간단히 요약 (1-2문장, 모든 티켓에서 항상 작성)
  * SIMPLE_ANSWER: 간단한 반응/인사라도 "고객이 무엇을 확인/동의하는지" 또는 "이전 대화 맥락에서 무엇을 하고 있었는지" 요약
  * AUTO_ANSWER, NEED_MORE_INFO, HUMAN_REQUIRED: 의도 분류나 문서 검색 결과를 바탕으로 고객이 무엇을 원하는지 요약
"""

# 에이전트 생성
# LangChain v1에서는 model과 system_prompt 파라미터 사용
# 참고: https://docs.langchain.com/oss/python/migrate/langchain-v1#migrate-to-create-agent
triage_agent_app = create_agent(
    model=llm,  # v1에서는 model 파라미터 사용
    tools=tools,
    system_prompt=SYSTEM_PROMPT,  # v1에서는 system_prompt 파라미터 사용 (state_modifier 제거)
)

def triage_agent_node(state: GraphState) -> GraphState:
    """
    LangGraph에서 호출되는 triage 노드.
    
    고객 발화와 대화 맥락을 분석하여 TriageDecisionType을 산출합니다.
    
    1) GraphState 안의 대화/현재 발화를 LangChain 메시지로 변환해서 triage_agent_app에 넘기고
    2) triage_agent_app 결과의 마지막 assistant 메시지에서 ticket/reason JSON을 파싱한 뒤
    3) GraphState에 triage_decision과 handover_reason을 채워서 반환한다.
    """
    user_message = state["user_message"]
    
    # 다음 턴 정보 수집 시작 플래그 확인 (명시적 플래그 방식)
    next_turn_start_collecting = state.get("next_turn_start_collecting", False)
    if next_turn_start_collecting:
        # 다음 턴부터 정보 수집 시작
        state["is_collecting_info"] = True
        state["info_collection_count"] = 0
        # 플래그 제거 (한 번만 사용)
        state["next_turn_start_collecting"] = False
        logger.info(f"정보 수집 시작 - 세션: {state.get('session_id', 'unknown')}, next_turn_start_collecting 플래그 확인")
    
    try:
        # 1. GraphState -> LangChain messages 변환
        lc_messages: List[Any] = []

        # (1) 시스템 메시지: triage 룰 설명
        lc_messages.append(SystemMessage(content=SYSTEM_PROMPT))

        # (2) 기존 대화 히스토리 (최대 10개만 사용 - 토큰 비용 절약)
        conversation_history = state.get("conversation_history", [])
        # 최근 10개 메시지만 선택 (최신 메시지부터)
        recent_messages = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        
        for msg in recent_messages:
            role = msg.get("role")
            message_text = msg.get("message", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=message_text))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=message_text))

            # 필요하면 system, tool 등도 추가

        # (3) 이번 턴 사용자 발화
        lc_messages.append(HumanMessage(content=user_message))

        # 2. triage_agent_app 호출 (ReAct + tools 자동 수행)
        result = triage_agent_app.invoke({"messages": lc_messages})

        # 3. Tool 호출 결과 추출 및 저장
        intent_top3 = None
        retrieved_docs = []
        
        # ToolMessage에서 결과 추출
        for msg in result["messages"]:
            if isinstance(msg, ToolMessage):
                tool_name = getattr(msg, 'name', None) or ''
                
                # intent_classification_tool 결과 추출
                if 'intent_classification' in tool_name or 'classify_intent' in tool_name:
                    if isinstance(msg.content, str):
                        intent_top3 = msg.content
                        logger.debug(f"Intent 분류 결과 추출: {intent_top3[:100] if intent_top3 else 'None'}")
                
                # rag_search_tool 결과 추출
                elif 'rag_search' in tool_name or 'search_rag' in tool_name:
                    if isinstance(msg.content, str):
                        retrieved_docs = parse_rag_result(msg.content)
                        logger.debug(f"RAG 검색 결과 추출: {len(retrieved_docs)} documents")
        
        # 의도 분류 결과 파싱 및 저장
        if intent_top3:
            try:
                intent_classifications_list = json.loads(intent_top3)
                # Top 3 전체 결과 저장
                state["intent_classifications"] = intent_classifications_list
                
                # 첫 번째 결과에서 context_intent와 intent_confidence 추출
                if intent_classifications_list and len(intent_classifications_list) > 0:
                    first_result = intent_classifications_list[0]
                    state["context_intent"] = first_result.get("intent", "")
                    state["intent_confidence"] = first_result.get("confidence", 0.0)
                else:
                    state["context_intent"] = None
                    state["intent_confidence"] = 0.0
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Intent 분류 결과 파싱 실패: {str(e)}", exc_info=True)
                state["context_intent"] = None
                state["intent_confidence"] = 0.0
                state["intent_classifications"] = None
        else:
            state["context_intent"] = None
            state["intent_confidence"] = 0.0
            state["intent_classifications"] = None
        
        # RAG 검색 결과 저장 (top3 문서 내용 포함)
        state["retrieved_documents"] = retrieved_docs
        
        # rag_best_score, rag_low_confidence 계산
        if retrieved_docs:
            state["rag_best_score"] = max(doc["score"] for doc in retrieved_docs)
            state["rag_low_confidence"] = state["rag_best_score"] < 0.2
        else:
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True

        # 5. 마지막 assistant 메시지에서 JSON 파싱
        # ReAct 에이전트는 ToolMessage와 AIMessage가 섞여 있을 수 있으므로
        # 역순으로 순회하여 마지막 AIMessage를 찾음
        final_msg = None
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                final_msg = msg
                break
        
        if final_msg is None:
            logger.error("triage_agent_node: AIMessage를 찾을 수 없음")
            raise ValueError("LLM 응답에서 AIMessage를 찾을 수 없습니다.")
        
        content = final_msg.content
        print(content)

        def _parse_json_payload(payload: Any) -> Dict[str, Any]:
            """LLM 응답(payload)을 JSON으로 파싱 (문자열/ContentBlock 리스트 모두 지원)."""
            if isinstance(payload, str):
                if not payload.strip():
                    logger.error("triage_agent_node: LLM 응답이 비어 있습니다 (str). payload=%r", payload)
                    raise ValueError("LLM 응답이 비어 있습니다.")
                return json.loads(payload)

            # LangChain v1에서 content가 ContentBlock 리스트로 반환될 수 있음
            if isinstance(payload, list):
                pieces: List[str] = []
                for block in payload:
                    # dict 형태 (구버전) 또는 ContentBlock 객체 모두 지원
                    text = None
                    if isinstance(block, dict):
                        text = block.get("text")
                    elif hasattr(block, "text"):
                        text = getattr(block, "text")
                    if text:
                        pieces.append(text)

                combined = "".join(pieces).strip()
                if not combined:
                    logger.error("triage_agent_node: LLM 응답에서 텍스트 블록을 찾지 못했습니다. payload=%r", payload)
                    raise ValueError("LLM 응답에서 텍스트 블록을 찾을 수 없습니다.")
                return json.loads(combined)

            logger.error("triage_agent_node: 지원되지 않는 content 타입: %s (payload=%r)", type(payload), payload)
            raise ValueError(f"지원되지 않는 content 타입: {type(payload)}")

        try:
            parsed = _parse_json_payload(content)
        except Exception as exc:
            logger.error("triage_agent_node: 응답 JSON 파싱 실패: %s", exc, exc_info=True)
            raise

        ticket_str: str = parsed.get("ticket", "")
        reason: str = parsed.get("reason", "")
        customer_intent_summary: str = parsed.get("customer_intent_summary", "")

        # 6. GraphState에 triage 결과 반영 (TriageDecisionType 산출)
        try:
            triage_decision = TriageDecisionType(ticket_str)
            state["triage_decision"] = triage_decision
            logger.info(f"Triage 결정 완료: {ticket_str} - 세션={state.get('session_id', 'unknown')}")
        except Exception:
            logger.warning("Unknown ticket type from LLM: %s", ticket_str)
            triage_decision = TriageDecisionType.SIMPLE_ANSWER  # fallback
            state["triage_decision"] = triage_decision

        state["handover_reason"] = reason
        state["customer_intent_summary"] = customer_intent_summary if customer_intent_summary else None

        # intent 필드 설정 (기본값만 설정, 나중에 감성분석 완료 후 구현 예정)
        state["intent"] = IntentType.INFO_REQ
        
        # 정보 수집 카운트: is_collecting_info=True일 때 고객 메시지가 들어올 때마다 카운트 증가
        # (HUMAN_REQUIRED 메시지 이후부터 고객 채팅이 들어올 때마다 카운트)
        is_collecting_info = state.get("is_collecting_info", False)
        if is_collecting_info:
            current_count = state.get("info_collection_count", 0)
            state["info_collection_count"] = current_count + 1
            logger.info(f"정보 수집 카운트 증가 - 세션: {state.get('session_id', 'unknown')}, 카운트: {state['info_collection_count']}")

    except Exception as e:
        # 에러 발생 시 기본값 (챗봇으로 처리)
        error_msg = str(e)
        logger.error(f"판단 에이전트 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
        
        # 연결 오류인 경우 특별 처리
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            logger.error(f"LM Studio 연결 오류 - 세션: {state.get('session_id', 'unknown')}, LM Studio가 실행 중인지 확인하세요")
        
        state["triage_decision"] = TriageDecisionType.SIMPLE_ANSWER  # 에러 시 기본값
        state["handover_reason"] = None
        state["customer_intent_summary"] = None
        state["intent"] = IntentType.INFO_REQ  # 기본값
        state["context_intent"] = None
        state["intent_confidence"] = 0.0
        state["intent_classifications"] = None
        state["retrieved_documents"] = []
        state["rag_best_score"] = None
        state["rag_low_confidence"] = True
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["decision_error"] = error_msg
    
    return state

