# ai_engine/graph/nodes/answer_agent.py

"""챗봇 답변 생성 에이전트: GPT 모델 호출."""

from __future__ import annotations
from langchain_openai import ChatOpenAI
from ai_engine.graph.state import GraphState
from app.schemas.chat import SourceDocument

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

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
    answer = llm.invoke(prompt).content
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
    
    return state