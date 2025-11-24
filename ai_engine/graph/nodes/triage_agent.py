# ai_engine/graph/nodes/triage_agent.py

from __future__ import annotations
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
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
        
        # 직접적인 상담원 연결 요청이면 RAG 검색 없이 바로 HUMAN_REQUIRED 반환
        if is_direct_handover_request:
            state["context_intent"] = "상담원 연결 요청"
            state["retrieved_documents"] = []
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True
            state["triage_decision"] = TriageDecisionType.HUMAN_REQUIRED
            state["requires_consultant"] = True
            state["handover_reason"] = "고객이 직접 상담원 연결을 요청함"
            state["intent"] = IntentType.HUMAN_REQ
            logger.info(f"직접 상담원 연결 요청 감지 - HUMAN_REQUIRED: 세션={state.get('session_id', 'unknown')}, 메시지='{user_message}'")
            return state
        
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
        
        # 상태 업데이트
        state["context_intent"] = context_intent
        state["retrieved_documents"] = retrieved_docs
        if retrieved_docs:
            state["rag_best_score"] = max(doc["score"] for doc in retrieved_docs)
            # 유사도 임계값 기준: 0.2 이상이면 AUTO_HANDLE_OK (프롬프트와 일치)
            state["rag_low_confidence"] = state["rag_best_score"] < 0.2
        else:
            state["rag_best_score"] = None
            state["rag_low_confidence"] = True
        
        # Tool 결과를 기반으로 프롬프트 구성
        intent_info = f"문맥 의도 분류 결과: {context_intent}"
        rag_info = ""
        if retrieved_docs:
            rag_info = f"\n\n[검색된 문서] (최고 유사도: {state['rag_best_score']:.2f})\n"
            rag_info += "=" * 80 + "\n"
            for i, doc in enumerate(retrieved_docs[:5], 1):  # 상위 5개 문서 포함
                rag_info += f"\n[문서 {i}]\n"
                rag_info += f"출처: {doc['source']}\n"
                rag_info += f"페이지: {doc['page']}\n"
                rag_info += f"유사도 점수: {doc['score']:.3f}\n"
                rag_info += f"문서 내용:\n{doc['content']}\n"  # 전체 내용 포함
                rag_info += "-" * 80 + "\n"
        else:
            rag_info = "\n\n[검색된 문서] 없음 (관련 문서를 찾지 못했습니다)"
        
        # System 메시지로 역할 정의
        system_message = SystemMessage(content="""당신은 고객 질문을 분석하여 처리 방식을 결정하는 Triage 에이전트입니다.

문맥 의도는 질문의 주제를 나타냅니다 (예: "대출", "예금", "카드론" 등).
검색된 문서에는 출처, 페이지, 유사도 점수(0.0~1.0), 그리고 **전체 문서 내용**이 포함되어 있습니다.

**판단 기준 (우선순위 순서대로 적용):**

**1단계: 유사도 점수 기준 분류**

가장 높은 유사도 점수(최고 유사도)를 확인하세요.

- **최고 유사도 ≥ 0.2인 경우:**
  → 기본적으로 **AUTO_HANDLE_OK**로 판단
  - 단, 아래 2단계의 예외 조건이 있으면 해당 기준 우선 적용

- **최고 유사도 < 0.2인 경우 또는 검색 결과가 없는 경우:**
  → 아래 2단계로 진행하여 NEED_MORE_INFO 또는 HUMAN_REQUIRED 판단

**2단계: 예외 조건 확인 (유사도와 관계없이 우선 적용)**

다음 조건 중 하나라도 해당되면 **즉시 HUMAN_REQUIRED**로 판단:
- 고객 메시지에 명확한 불만이나 민원 표현이 있는 경우 (예: "불만", "민원", "화가 났어요", "항의", "불편")
- 복잡한 계약 변경이나 대출 신청 같은 실무 처리 업무인 경우
- 개인정보 확인이나 본인 인증이 필요한 경우
- 문서 내용을 읽어보니 내용만으로는 처리할 수 없는 복잡한 업무인 경우 (예: 계약 해지, 대출 신청, 계좌 개설 등 실제 거래)

**3단계: 유사도 < 0.2인 경우의 세부 분류**

유사도가 낮거나 검색 결과가 없지만, 위 예외 조건에 해당하지 않는 경우:

- **NEED_MORE_INFO (추가 정보 필요):**
  - 질문이 모호하여 추가 질문으로 답변 가능할 수 있는 경우 (예: "대출이 궁금해요" → 어떤 대출인지 물어보면 답변 가능)
  - 고객의 의도가 명확하지 않아 추가 질문이 필요한 경우
  - 문서 내용이 부분적으로만 관련 있거나, 고객의 구체적인 상황을 파악하기 위해 추가 정보가 필요한 경우
  - 즉, **고객이 추가 정보를 제공하면 챗봇이 답변할 수 있는 경우**

- **HUMAN_REQUIRED (상담사 연결 필요):**
  - 검색 결과가 전혀 없고, 질문 내용만으로는 추가 질문으로도 해결하기 어려운 경우
  - 문서 내용을 읽어보니 질문과 전혀 관련 없는 경우
  - 개인화된 정보나 실시간 데이터가 필요한 경우 (예: "내 계좌 잔액이 얼마야?", "내 대출 잔액 확인")
  - 즉, **챗봇으로는 해결할 수 없고 상담사의 직접 개입이 필요한 경우**

**판단 프로세스 요약:**
1. 먼저 최고 유사도 점수를 확인
2. 예외 조건(불만/민원/복잡 업무 등) 확인 → 있으면 HUMAN_REQUIRED
3. 유사도 ≥ 0.2 → AUTO_HANDLE_OK (단, 예외 조건 제외)
4. 유사도 < 0.2 → 추가 정보로 해결 가능한지 판단 → 가능하면 NEED_MORE_INFO, 불가능하면 HUMAN_REQUIRED

다음 형식으로만 답변해주세요 (반드시 정확히 이 형식으로):
- "AUTO_HANDLE_OK"
- "NEED_MORE_INFO"
- "HUMAN_REQUIRED"

다른 설명이나 추가 텍스트 없이 위 세 가지 중 하나만 답변하세요.
""")
        
        human_message = HumanMessage(content=f"""다음 고객 질문을 분석해주세요:

[고객 질문]
{user_message}

{intent_info}
{rag_info}

위 정보를 바탕으로 처리 방식을 결정해주세요. AUTO_HANDLE_OK, NEED_MORE_INFO, HUMAN_REQUIRED 중 하나만 답변하세요.""")
        
        # LLM으로 판단 (검색 결과 유무와 관계없이)
        logger.info(f"LLM 판단 시작 - 세션={state.get('session_id', 'unknown')}, 검색 결과 수={len(retrieved_docs) if retrieved_docs else 0}")
        response = llm.invoke([system_message, human_message])
        llm_response = response.content.strip().upper()
        
        # 초기값 설정
        triage_decision = None
        requires_consultant = False
        intent_type = None
        
        # LLM 응답 파싱
        if "AUTO_HANDLE_OK" in llm_response:
            triage_decision = TriageDecisionType.AUTO_HANDLE_OK
            requires_consultant = False
            intent_type = IntentType.INFO_REQ
        elif "NEED_MORE_INFO" in llm_response:
            triage_decision = TriageDecisionType.NEED_MORE_INFO
            requires_consultant = False
            intent_type = IntentType.INFO_REQ
        elif "HUMAN_REQUIRED" in llm_response:
            triage_decision = TriageDecisionType.HUMAN_REQUIRED
            requires_consultant = True
            # 민원 관련 키워드가 있으면 COMPLAINT, 아니면 HUMAN_REQ
            complaint_keywords = ["불만", "불편", "화가", "문제", "민원", "항의", "불평"]
            is_complaint = any(keyword in user_message for keyword in complaint_keywords)
            if is_complaint:
                intent_type = IntentType.COMPLAINT
            else:
                intent_type = IntentType.HUMAN_REQ
        else:
            # 파싱 실패 시 기본값 (HUMAN_REQUIRED)
            triage_decision = TriageDecisionType.HUMAN_REQUIRED
            requires_consultant = True
            intent_type = IntentType.HUMAN_REQ
            logger.warning(f"LLM 응답 파싱 실패 - 기본값 HUMAN_REQUIRED 사용: 세션={state.get('session_id', 'unknown')}, 응답={llm_response[:100]}")
        
        logger.info(f"LLM 판단 결과: 세션={state.get('session_id', 'unknown')}, triage_decision={triage_decision}, 응답={llm_response[:100]}")
        
        # 상태 업데이트
        state["triage_decision"] = triage_decision
        state["requires_consultant"] = requires_consultant
        state["handover_reason"] = f"Triage 결정: {triage_decision.value}" if requires_consultant else None
        state["intent"] = intent_type
            
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
    0.2
    return state

