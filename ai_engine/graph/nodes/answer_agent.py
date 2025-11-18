# ai_engine/graph/nodes/answer_agent.py

"""챗봇 답변 생성 에이전트: GPT 모델 호출."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from app.schemas.chat import SourceDocument
from ai_engine.prompts.templates import SYSTEM_PROMPT

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

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
        
        # LLM 호출 (tool 호출 없이 단순 답변 생성)
        response = llm.invoke([system_message, human_message])
        answer = response.content
        
        state["ai_message"] = answer
        
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
        # 에러 발생 시 기본 응답
        state["ai_message"] = "죄송합니다. 답변을 생성하는 중 오류가 발생했습니다."
        state["source_documents"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["answer_error"] = str(e)
    
    return state