# ai_engine/graph/nodes/decision_agent.py

from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from ai_engine.graph.tools import intent_classification_tool, rag_search_tool
from ai_engine.graph.tools.rag_search_tool import parse_rag_result
from app.schemas.common import IntentType

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)


def decision_agent_node(state: GraphState) -> GraphState:
    """고객 질문을 판단하여 상담사 연결 필요 여부를 결정하는 노드.
    
    intent_classification_tool과 rag_search_tool을 직접 호출하여 
    의도 분류와 RAG 검색 결과를 얻은 후, 그 결과를 기반으로 상담사 이관 필요 여부를 결정합니다.
    """
    user_message = state["user_message"]
    
    try:
        # Tool을 직접 호출 (LLM을 거치지 않고)
        context_intent = intent_classification_tool.invoke({"user_message": user_message})
    
        rag_result_json = rag_search_tool.invoke({"query": user_message, "top_k": 5})
        retrieved_docs = parse_rag_result(rag_result_json)
        
        # 상태 업데이트
        state["context_intent"] = context_intent
        state["retrieved_documents"] = retrieved_docs
        if retrieved_docs:
            state["rag_best_score"] = max(doc["score"] for doc in retrieved_docs)
            state["rag_low_confidence"] = state["rag_best_score"] < 0.7  # 임계값 설정
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

문맥 의도는 질문의 주제를 나타냅니다 (예: "대출", "예금", "대출 상환" 등).
이를 기반으로 상담사 연결 필요 여부를 판단하세요.

다음 기준에 따라 판단하세요:

상담사 연결이 필요한 경우:
- 문맥 의도가 "상담" 또는 고객이 상담사를 직접 요청한 경우
- 고객 메시지에 불만이나 민원 표현이 있는 경우
- RAG 검색 결과가 없거나 신뢰도가 낮은 경우 (유사도 < 0.7)
- 복잡한 민원이나 계약 변경 요청인 경우 (예: "대출 상환" 같은 복잡한 절차)

챗봇으로 처리 가능한 경우:
- 단순 정보 문의이고 RAG 검색 결과가 충분한 경우
- FAQ 형태의 단순한 질문인 경우

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

상담사 연결 필요 여부를 판단해주세요.""")
        
        # LLM 호출 (단순 판단만 수행)
        response = llm.invoke([system_message, human_message])
        final_response = response.content
        
        # 최종 판단: 상담사 연결 필요 여부 파싱
        requires_consultant = "상담사 연결 필요" in final_response
        
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
        state["requires_consultant"] = False
        state["handover_reason"] = None
        state["intent"] = IntentType.INFO_REQ  # 기본값
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["decision_error"] = str(e)
    
    return state

