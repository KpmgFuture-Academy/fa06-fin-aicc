# ai_engine/graph/nodes/chat_db_storage.py

from __future__ import annotations
from datetime import datetime
import json
from typing import Optional
from ai_engine.graph.state import GraphState, ConversationMessage
from app.core.database import SessionLocal
from app.models.chat_message import ChatSession, ChatMessage, MessageRole
from app.schemas.common import IntentType, ActionType


def chat_db_storage_node(state: GraphState) -> GraphState:
    """상담 내용을 데이터베이스에 저장하고 conversation_history를 업데이트하는 노드."""
    session_id = state.get("session_id")
    user_message = state.get("user_message")
    ai_message = state.get("ai_message")
    intent = state.get("intent")
    suggested_action = state.get("suggested_action")
    source_documents = state.get("source_documents", [])
    
    if not session_id:
        # 세션 ID가 없으면 에러
        state["error_message"] = "세션 ID가 없습니다."
        state["db_stored"] = False
        return state
    
    db = SessionLocal()
    try:
        # 세션 조회 또는 생성
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not chat_session:
            # 새 세션 생성
            chat_session = ChatSession(
                session_id=session_id,
                is_active=1
            )
            db.add(chat_session)
            db.flush()  # ID를 얻기 위해 flush
        
        # 사용자 메시지 저장
        if user_message:
            user_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.USER,
                message=user_message,
                intent=intent.value if intent else None,
                created_at=datetime.utcnow()
            )
            db.add(user_msg)
        
        # AI 답변 저장
        if ai_message:
            source_docs_json = None
            if source_documents:
                # source_documents를 JSON으로 변환
                source_docs_json = json.dumps([
                    {
                        "source": doc.source if hasattr(doc, 'source') else doc.get("source", ""),
                        "page": doc.page if hasattr(doc, 'page') else doc.get("page", 0),
                        "score": doc.score if hasattr(doc, 'score') else doc.get("score", 0.0)
                    }
                    for doc in source_documents
                ], ensure_ascii=False)
            
            ai_msg = ChatMessage(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                message=ai_message,
                suggested_action=suggested_action.value if suggested_action else None,
                source_documents=source_docs_json,
                created_at=datetime.utcnow()
            )
            db.add(ai_msg)
        
        # 세션 업데이트 시간 갱신
        chat_session.updated_at = datetime.utcnow()
        
        # 커밋
        db.commit()
        
        # DB에서 최신 conversation_history 로드
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        # conversation_history 업데이트
        conversation_history: list[ConversationMessage] = []
        for msg in messages:
            conversation_history.append(ConversationMessage(
                role=msg.role.value,
                message=msg.message,
                timestamp=msg.created_at.isoformat()
            ))
        
        state["conversation_history"] = conversation_history
        state["db_stored"] = True
        
    except Exception as e:
        db.rollback()
        state["error_message"] = f"DB 저장 중 오류 발생: {str(e)}"
        state["db_stored"] = False
        # 에러가 발생해도 conversation_history는 메모리에서 유지
        if "conversation_history" not in state:
            state["conversation_history"] = []
        
        # 메모리에서 conversation_history 업데이트 (fallback)
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
    finally:
        db.close()
    
    # is_session_end는 기본적으로 False
    if "is_session_end" not in state:
        state["is_session_end"] = False
    
    return state

