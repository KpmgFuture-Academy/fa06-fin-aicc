# ai_engine/graph/nodes/consultation_db_storage.py

from __future__ import annotations
from datetime import datetime
from ai_engine.graph.state import GraphState, ConversationMessage

def chat_db_storage_node(state: GraphState) -> GraphState:
    """상담 내용을 데이터베이스에 저장하고 conversation_history를 업데이트하는 노드."""
    # TODO: DB 저장 로직 구현
    
    # conversation_history 초기화 (없으면 빈 리스트)
    if "conversation_history" not in state:
        state["conversation_history"] = []
    
    # 현재 턴의 사용자 메시지와 AI 답변을 history에 추가
    user_message = state.get("user_message")
    ai_message = state.get("ai_message")
    timestamp = datetime.now().isoformat()
    
    if user_message:
        state["conversation_history"].append(ConversationMessage(
            role="user",
            message=user_message,
            timestamp=timestamp
        ))
    
    if ai_message:
        state["conversation_history"].append(ConversationMessage(
            role="assistant",
            message=ai_message,
            timestamp=timestamp
        ))
    
    # DB 저장 완료 플래그 설정
    state["db_stored"] = True
    
    # is_session_end는 기본적으로 False (외부에서 설정하거나 로직에 따라 결정)
    # 만약 설정되지 않았다면 기본값 False
    if "is_session_end" not in state:
        state["is_session_end"] = False
    
    return state

