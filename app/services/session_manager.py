"""세션 관리 서비스
DB에서 conversation_history를 로드하는 기능 제공
"""

import logging
from typing import List
from ai_engine.graph.state import ConversationMessage
from app.core.database import SessionLocal
from app.models.chat_message import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class SessionManager:
    """세션별 대화 이력 관리 (DB 기반)"""
    
    def get_conversation_history(self, session_id: str) -> List[ConversationMessage]:
        """세션의 대화 이력을 DB에서 조회"""
        db = SessionLocal()
        try:
            # 세션이 존재하는지 확인
            chat_session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.is_active == 1
            ).first()
            
            if not chat_session:
                return []
            
            # 메시지 조회
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            # ConversationMessage 리스트로 변환
            conversation_history: List[ConversationMessage] = []
            for msg in messages:
                conversation_history.append(ConversationMessage(
                    role=msg.role.value,
                    message=msg.message,
                    timestamp=msg.created_at.isoformat()
                ))
            
            return conversation_history
            
        except Exception as e:
            # 에러 발생 시 빈 리스트 반환
            logger.error(f"세션 이력 조회 중 오류 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
            return []
        finally:
            db.close()
    
    def save_conversation_history(
        self, 
        session_id: str, 
        conversation_history: List[ConversationMessage]
    ) -> None:
        """세션의 대화 이력 저장 (chat_db_storage_node에서 처리하므로 여기서는 no-op)"""
        # chat_db_storage_node에서 이미 DB에 저장하므로
        # 여기서는 별도 저장 불필요
        pass
    
    def get_session_exists(self, session_id: str) -> bool:
        """세션이 존재하는지 확인"""
        db = SessionLocal()
        try:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.is_active == 1
            ).first()
            return session is not None
        finally:
            db.close()
    
    def deactivate_session(self, session_id: str) -> None:
        """세션 비활성화 (상담 종료 시)"""
        db = SessionLocal()
        try:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            if session:
                session.is_active = 0
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"세션 비활성화 중 오류 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    def get_active_session_count(self) -> int:
        """현재 활성 세션 수"""
        db = SessionLocal()
        try:
            return db.query(ChatSession).filter(ChatSession.is_active == 1).count()
        finally:
            db.close()


# 전역 세션 매니저 인스턴스
session_manager = SessionManager()

