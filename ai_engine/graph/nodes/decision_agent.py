# ai_engine/graph/nodes/decision_agent.py

from __future__ import annotations

from langchain_openai import ChatOpenAI
from ai_engine.graph.state import GraphState

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)


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
        response = llm.invoke(prompt).content
        
        # LLM 응답을 파싱하여 판단
        if "상담사 연결 필요" in response or "상담사" in response:
            state["requires_consultant"] = True
            state["handover_reason"] = response.strip()
        else:
            state["requires_consultant"] = False
            state["handover_reason"] = None
            
    except Exception as e:
        # 에러 발생 시 기본값 (챗봇으로 처리)
        state["requires_consultant"] = False
        state["handover_reason"] = None
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["decision_error"] = str(e)
    
    return state

