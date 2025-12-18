# ai_engine/graph/nodes/triage_agent.py

from __future__ import annotations
import json
import logging
import re
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
🚨 절대 규칙 (반드시 준수):
- 당신은 "분류기"입니다. 고객에게 직접 답변하는 것은 금지됩니다.
- 출력은 반드시 JSON 형식만 허용됩니다. 다른 텍스트 출력 금지!
- 도구 결과를 보고 "답변을 작성"하지 마세요. "분류 판단"만 하세요.

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

4) 상담사 이관이 필요한 경우 (HUMAN_REQUIRED)
   아래 조건 중 하나라도 해당하면 반드시 HUMAN_REQUIRED를 선택하세요:

   A) **실제 처리/조치가 필요한 업무** (가장 중요!)
      - 보이스피싱/금융사기 의심 → 반드시 HUMAN_REQUIRED
      - 해외 부정결제 신고 → 반드시 HUMAN_REQUIRED
      - 카드 해지/탈퇴 요청 → 반드시 HUMAN_REQUIRED
      - 결제 취소/환불 요청 → 반드시 HUMAN_REQUIRED
      - 이의제기/분쟁 해결 요청 → 반드시 HUMAN_REQUIRED
      ⚠️ 이런 업무는 AI가 "처리하겠습니다"라고 말할 수 없습니다!
      ⚠️ 정보만 안내하는 것과 실제 처리는 다릅니다!

   ✅ **AUTO_ANSWER로 처리해야 하는 업무** (FAQ 기반 안내 - 절대 HUMAN_REQUIRED 아님!):

      🚨 **카드 분실/도난 관련은 무조건 AUTO_ANSWER입니다!** 🚨
      - "카드 분실했어요", "카드 잃어버렸어요" → AUTO_ANSWER
      - "카드 도난당했어요" → AUTO_ANSWER
      - "분실신고 해주세요", "카드 정지해주세요" → AUTO_ANSWER
      - "카드 임시 정지하고 싶어요" → AUTO_ANSWER
      - "분실 카드 찾았어요, 해제해주세요" → AUTO_ANSWER
      - "카드 재발급 받고 싶어요" → AUTO_ANSWER

      ❗ 이유: 하나카드 앱/ARS에서 고객이 직접 분실신고, 정지, 해제, 재발급 모두 가능!
      ❗ AI는 "방법"을 안내하면 됩니다. 상담원이 대신 처리할 필요 없음!

      ※ 고객이 "정지해주세요", "신고해주세요"라고 해도 방법을 안내하면 되는 경우 AUTO_ANSWER!

   ⚠️ **HUMAN_REQUIRED가 아닌 경우 (정보 안내로 처리 가능)**:
      - 결제일 변경 방법 안내 → AUTO_ANSWER (앱/웹에서 고객이 직접 변경 가능)
      - 한도 변경 방법 안내 → AUTO_ANSWER (앱/웹에서 고객이 직접 변경 가능)
      - 개인정보 변경 방법 안내 → AUTO_ANSWER (앱/웹에서 고객이 직접 변경 가능)
      - 이용내역 조회 방법 안내 → AUTO_ANSWER
      - 포인트 조회/사용 방법 안내 → AUTO_ANSWER
      고객이 "~하고 싶어요", "~변경하고 싶습니다"라고 해도 방법을 안내하면 되는 경우 AUTO_ANSWER!

   B) **고객이 상담사 연결을 명시적으로 요청한 경우**
      - "상담사 연결해주세요", "사람과 통화하고 싶어요" 등

   C) **강한 불만/민원으로 자동 응답이 부적절한 경우**
      - 이미 여러 차례 안내했으나 해결되지 않아 고객이 인내심을 잃은 상황

   위 조건에 해당하면 intent_classification_tool, rag_search_tool을 호출하지 말고,
   바로 HUMAN_REQUIRED 티켓 JSON을 출력한다.

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

단, HUMAN_REQUIRED를 선택할 때는 아래 세 질문을 참고해서 판단한다.
- "이 업무는 상담원만 처리 가능한가?" (보이스피싱/금융사기 피해 신고, 부정사용 이의제기, 가맹점 결제 취소 중재, 민원/불만 접수 등)
- "고객이 상담사 연결을 명시적으로 요청했는가?"
- "자동 응답으로 해결할 수 없음이 반복적으로 확인되었는가?"
세 질문 중 하나라도 "예"라면 HUMAN_REQUIRED를 선택한다.

🚨🚨🚨 **절대 HUMAN_REQUIRED로 분류하면 안 되는 케이스** 🚨🚨🚨
다음 키워드가 포함된 요청은 무조건 AUTO_ANSWER입니다:
- 카드 분실, 카드 도난, 분실신고, 카드 정지, 카드 해제
- 한도 변경, 한도 조회, 한도 상향
- 결제일 변경, 결제일 조회
- 카드 재발급
→ 이 업무들은 앱/ARS에서 고객이 직접 처리 가능하므로 AUTO_ANSWER로 방법을 안내!

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

⚠️ 중요 (위반 시 시스템 오류 발생):
- 절대 고객에게 직접 답변하지 마세요!
- 도구 결과(RAG 검색 결과 등)를 보고 "답변"을 작성하면 안 됩니다.
- 도구 결과는 오직 "어떤 티켓으로 분류할지" 판단하는 데만 사용하세요.
- 당신이 출력할 수 있는 것은 오직 아래 JSON 형식뿐입니다:
{"ticket": "...", "reason": "...", "customer_intent_summary": "..."}
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

    try:
        # 0. 의도 분류 먼저 수행 (HUMAN_REQUIRED 케이스에서도 context_intent 기록을 위해)
        # LLM이 HUMAN_REQUIRED로 빠르게 판단하면 tool 호출을 스킵하므로, 여기서 강제 호출
        intent_top3_prefetch = None
        try:
            logger.info(f"의도 분류 사전 호출 - 메시지: {user_message[:50]}...")
            intent_result = intent_classification_tool.invoke(user_message)
            if isinstance(intent_result, str):
                intent_top3_prefetch = intent_result
                logger.info(f"의도 분류 사전 호출 완료: {intent_top3_prefetch[:100] if intent_top3_prefetch else 'None'}")
        except Exception as e:
            logger.warning(f"의도 분류 사전 호출 실패 (계속 진행): {e}")

        # 1. GraphState -> LangChain messages 변환
        lc_messages: List[Any] = []

        # (1) 시스템 메시지는 create_agent의 system_prompt로 이미 전달됨
        # 중복으로 추가하지 않음 (중복 시 LLM이 혼란할 수 있음)

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

        # LLM이 intent_classification_tool을 호출하지 않은 경우 (HUMAN_REQUIRED 등)
        # 사전 호출한 결과를 사용하여 context_intent 기록
        if intent_top3 is None and intent_top3_prefetch is not None:
            intent_top3 = intent_top3_prefetch
            logger.info(f"LLM이 intent tool 미호출 → 사전 호출 결과 사용: {intent_top3[:100] if intent_top3 else 'None'}")
        
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
        # rerank_score가 있으면 우선 사용, 없으면 기존 score 사용
        if retrieved_docs:
            state["rag_best_score"] = max(
                doc.get("rerank_score", doc.get("score", 0)) for doc in retrieved_docs
            )
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

            # 코드 레벨 오버라이드: 특정 키워드가 포함된 경우 HUMAN_REQUIRED → AUTO_ANSWER로 강제 변환
            # LLM이 프롬프트를 무시하고 HUMAN_REQUIRED로 분류하는 케이스 방지
            if triage_decision == TriageDecisionType.HUMAN_REQUIRED:
                user_message_lower = user_message.lower() if user_message else ""

                # 🚨 긴급 상황 키워드: 즉시 상담사 연결 (슬롯 수집 없이)
                # 보이스피싱, 금융사기 등은 즉시 상담사 연결 필요
                urgent_keywords = [
                    "보이스피싱", "보이스 피싱", "피싱", "사기", "금융사기", "금융 사기",
                    "해킹", "불법", "도용", "명의도용", "명의 도용",
                    "협박", "위협", "급하", "긴급", "응급",
                ]
                is_urgent_case = any(kw in user_message_lower for kw in urgent_keywords)

                # 긴급 상황이면 HUMAN_REQUIRED 유지 + 긴급 플래그 설정
                if is_urgent_case:
                    logger.info(f"긴급 상황 감지: HUMAN_REQUIRED 유지 (슬롯 수집 스킵) - 세션={state.get('session_id', 'unknown')}, 원문={user_message}")
                    state["is_urgent_handover"] = True  # 긴급 핸드오버 플래그
                    reason = f"[긴급] {reason} → 보이스피싱/사기 의심으로 즉시 상담사 연결"
                else:
                    # 앱/ARS에서 고객이 직접 처리 가능한 업무 키워드
                    auto_answer_keywords = [
                        "분실", "도난", "잃어버", "정지", "해제",  # 카드 분실/도난/정지
                        "한도", "한도 변경", "한도 조회", "한도 상향",  # 한도 관련
                        "결제일", "결제일 변경", "결제일 조회",  # 결제일 관련
                        "재발급",  # 카드 재발급
                    ]
                    # 상담원 연결 요청은 제외 (명시적 요청은 유지)
                    agent_request_keywords = ["상담사", "상담원", "사람", "연결"]

                    is_auto_answer_case = any(kw in user_message_lower for kw in auto_answer_keywords)
                    is_agent_request = any(kw in user_message_lower for kw in agent_request_keywords)

                    if is_auto_answer_case and not is_agent_request:
                        logger.info(f"오버라이드: HUMAN_REQUIRED → AUTO_ANSWER (키워드 매칭) - 세션={state.get('session_id', 'unknown')}, 원문={user_message}")
                        triage_decision = TriageDecisionType.AUTO_ANSWER
                        reason = f"[오버라이드] {reason} → 앱/ARS에서 직접 처리 가능한 업무로 AUTO_ANSWER로 변경"

            state["triage_decision"] = triage_decision
            logger.info(f"Triage 결정 완료: {triage_decision.value} - 세션={state.get('session_id', 'unknown')}")

            # AUTO_ANSWER인데 RAG 검색 결과가 없으면 강제로 RAG 검색 수행
            if triage_decision == TriageDecisionType.AUTO_ANSWER and not retrieved_docs:
                logger.info(f"AUTO_ANSWER인데 RAG 결과 없음 → RAG 검색 강제 실행 - 세션={state.get('session_id', 'unknown')}")
                try:
                    rag_result = rag_search_tool.invoke({"query": user_message})
                    if isinstance(rag_result, str):
                        retrieved_docs = parse_rag_result(rag_result)
                        state["retrieved_documents"] = retrieved_docs
                        if retrieved_docs:
                            state["rag_best_score"] = max(
                                doc.get("rerank_score", doc.get("score", 0)) for doc in retrieved_docs
                            )
                            state["rag_low_confidence"] = state["rag_best_score"] < 0.2
                            logger.info(f"RAG 강제 검색 완료: {len(retrieved_docs)}개 문서, best_score={state['rag_best_score']:.2f}")
                except Exception as rag_err:
                    logger.warning(f"RAG 강제 검색 실패: {rag_err}")

        except Exception:
            logger.warning("Unknown ticket type from LLM: %s", ticket_str)
            triage_decision = TriageDecisionType.SIMPLE_ANSWER  # fallback
            state["triage_decision"] = triage_decision

        state["handover_reason"] = reason
        state["customer_intent_summary"] = customer_intent_summary if customer_intent_summary else None

        # intent 필드 설정 (기본값만 설정, 나중에 감성분석 완료 후 구현 예정)
        state["intent"] = IntentType.INFO_REQ

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

