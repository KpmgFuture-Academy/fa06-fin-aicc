# ai_engine/graph/nodes/chat_db_storage.py

from __future__ import annotations
from datetime import datetime
import json
import logging
from typing import Optional
from ai_engine.graph.state import GraphState, ConversationMessage
from app.core.database import SessionLocal
from app.models.chat_message import ChatSession, ChatMessage, MessageRole
from app.schemas.common import IntentType, ActionType

logger = logging.getLogger(__name__)


def chat_db_storage_node(state: GraphState) -> GraphState:
    """상담 내용을 데이터베이스에 저장하고 conversation_history를 업데이트하는 노드."""
    session_id = state.get("session_id")
    logger.info(f"chat_db_storage_node 실행 - 세션: {session_id}")
    user_message = state.get("user_message")
    ai_message = state.get("ai_message")
    intent = state.get("intent")
    suggested_action = state.get("suggested_action")
    source_documents = state.get("source_documents", [])
    
    # HUMAN_REQUIRED 플로우 상태 필드
    is_human_required_flow = state.get("is_human_required_flow", False)
    customer_consent_received = state.get("customer_consent_received", False)
    collected_info = state.get("collected_info", {})
    info_collection_complete = state.get("info_collection_complete", False)
    triage_decision = state.get("triage_decision")
    
    if not session_id:
        # 세션 ID가 없으면 에러
        state["error_message"] = "세션 ID가 없습니다."
        state["db_stored"] = False
        return state
    
    db = SessionLocal()
    try:
        # ========== [chat_sessions 테이블] 세션 정보 저장 ==========
        # 세션 조회 또는 생성
        chat_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not chat_session:
            # [chat_sessions] 새 세션 INSERT
            chat_session = ChatSession(
                session_id=session_id,                    # session_id 컬럼
                is_active=1,                              # is_active 컬럼
                is_human_required_flow=1 if is_human_required_flow else 0,      # is_human_required_flow 컬럼
                customer_consent_received=1 if customer_consent_received else 0, # customer_consent_received 컬럼
                collected_info=json.dumps(collected_info, ensure_ascii=False) if collected_info else None,  # collected_info 컬럼 (JSON)
                info_collection_complete=1 if info_collection_complete else 0,   # info_collection_complete 컬럼
                triage_decision=triage_decision.value if triage_decision else None  # triage_decision 컬럼
            )
            db.add(chat_session)
            db.flush()  # ID를 얻기 위해 flush
        else:
            # [chat_sessions] 기존 세션 UPDATE - HUMAN_REQUIRED 플로우 상태 저장
            chat_session.is_human_required_flow = 1 if is_human_required_flow else 0
            chat_session.customer_consent_received = 1 if customer_consent_received else 0
            chat_session.collected_info = json.dumps(collected_info, ensure_ascii=False) if collected_info else None
            chat_session.info_collection_complete = 1 if info_collection_complete else 0
            if triage_decision:
                chat_session.triage_decision = triage_decision.value if hasattr(triage_decision, 'value') else str(triage_decision)
        
        # ========== [chat_messages 테이블] 대화 메시지 저장 ==========
        # [chat_messages] 사용자 메시지 INSERT (role=USER)
        if user_message:
            user_msg = ChatMessage(
                session_id=session_id,           # session_id 컬럼 (FK)
                role=MessageRole.USER,           # role 컬럼
                message=user_message,            # message 컬럼
                intent=intent.value if intent else None,  # intent 컬럼
                created_at=datetime.utcnow()     # created_at 컬럼
            )
            db.add(user_msg)
        
        # [chat_messages] AI 응답 INSERT (role=ASSISTANT)
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
                session_id=session_id,           # session_id 컬럼 (FK)
                role=MessageRole.ASSISTANT,      # role 컬럼
                message=ai_message,              # message 컬럼
                suggested_action=suggested_action.value if suggested_action else None,  # suggested_action 컬럼
                source_documents=source_docs_json,  # source_documents 컬럼 (JSON)
                created_at=datetime.utcnow()     # created_at 컬럼
            )
            db.add(ai_msg)
        
        # ========== DB 커밋 ==========
        # [chat_sessions] updated_at 컬럼 갱신
        chat_session.updated_at = datetime.utcnow()
        
        # 모든 변경사항 커밋 (chat_sessions + chat_messages)
        db.commit()
        
        logger.info(f"DB 저장 완료 - 세션: {session_id}, collected_info: {collected_info}")
        
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

