"""세션 관리 서비스
DB에서 conversation_history를 로드하는 기능 제공
"""

import json
import logging
from typing import List, Dict, Any, Optional
from ai_engine.graph.state import ConversationMessage
from app.core.database import SessionLocal
from app.models.chat_message import ChatSession, ChatMessage
from app.schemas.common import TriageDecisionType
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SessionManager:
    """세션별 대화 이력 관리 (DB 기반)"""
    
    def __init__(self):
        # 세션별 임시 메타데이터 저장 (메모리)
        self._session_metadata: Dict[str, Dict[str, Any]] = {}
    
    def store_session_metadata(self, session_id: str, summary: Optional[str], sentiment: Optional[str], keywords: List[str]):
        """세션의 요약 정보를 임시로 메모리에 저장"""
        self._session_metadata[session_id] = {
            "summary": summary,
            "sentiment": sentiment,
            "keywords": keywords
        }
        logger.debug(f"세션 메타데이터 저장 - 세션: {session_id}, summary: {summary[:50] if summary else None}...")
    
    def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """세션의 요약 정보를 메모리에서 조회"""
        metadata = self._session_metadata.get(session_id, {})
        logger.debug(f"세션 메타데이터 조회 - 세션: {session_id}, 존재: {bool(metadata)}")
        return metadata
    
    def clear_session_metadata(self, session_id: str):
        """세션의 요약 정보를 메모리에서 삭제"""
        if session_id in self._session_metadata:
            del self._session_metadata[session_id]
            logger.debug(f"세션 메타데이터 삭제 - 세션: {session_id}")
    
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
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """세션의 HUMAN_REQUIRED 플로우 상태를 DB에서 조회

        Note: is_active 조건 없이 조회합니다. HUMAN_REQUIRED 플로우 상태는
        세션의 활성화 여부와 관계없이 로드해야 정보 수집 플로우가 정상 작동합니다.

        Returns:
            Dict with keys:
            - is_human_required_flow: bool
            - customer_consent_received: bool
            - collected_info: dict
            - info_collection_complete: bool
            - triage_decision: Optional[TriageDecisionType]
        """
        db = SessionLocal()
        try:
            # is_active 조건 제거 - 플로우 상태는 활성화 여부와 무관하게 로드
            chat_session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if not chat_session:
                return {
                    "is_human_required_flow": False,
                    "customer_consent_received": False,
                    "collected_info": {},
                    "info_collection_complete": False,
                    "triage_decision": None
                }
            
            # collected_info JSON 파싱
            collected_info = {}
            if chat_session.collected_info:
                try:
                    collected_info = json.loads(chat_session.collected_info)
                except json.JSONDecodeError:
                    collected_info = {}
            
            # triage_decision 변환
            triage_decision = None
            if chat_session.triage_decision:
                try:
                    triage_decision = TriageDecisionType(chat_session.triage_decision)
                except ValueError:
                    triage_decision = None
            
            return {
                "is_human_required_flow": bool(chat_session.is_human_required_flow),
                "customer_consent_received": bool(chat_session.customer_consent_received),
                "collected_info": collected_info,
                "info_collection_complete": bool(chat_session.info_collection_complete),
                "triage_decision": triage_decision
            }
            
        except Exception as e:
            logger.error(f"세션 상태 조회 중 오류 - 세션: {session_id}, 오류: {str(e)}", exc_info=True)
            return {
                "is_human_required_flow": False,
                "customer_consent_received": False,
                "collected_info": {},
                "info_collection_complete": False,
                "triage_decision": None
            }
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
    
    def deactivate_inactive_sessions(self, threshold_minutes: int = 10) -> int:
        """마지막 메시지 시각 기준 무활동 세션 비활성화
        
        Returns:
            int: 비활성화된 세션 수
        """
        db = SessionLocal()
        deactivated = 0
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=threshold_minutes)
            
            # 활성 세션만 조회
            active_sessions = db.query(ChatSession).filter(
                ChatSession.is_active == 1
            ).all()
            
            for session in active_sessions:
                # 마지막 메시지 시각 조회 (없으면 세션 updated_at/created_at 사용)
                last_msg = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session.session_id
                ).order_by(ChatMessage.created_at.desc()).first()
                
                last_ts = (
                    last_msg.created_at if last_msg
                    else session.updated_at or session.created_at
                )
                
                if last_ts and last_ts < cutoff:
                    session.is_active = 0
                    session.updated_at = datetime.utcnow()
                    deactivated += 1
            
            if deactivated > 0:
                db.commit()
                logger.info(f"무활동 세션 {deactivated}개 비활성화 (기준: {threshold_minutes}분)")
            return deactivated
        except Exception as e:
            db.rollback()
            logger.error(f"무활동 세션 비활성화 중 오류: {str(e)}", exc_info=True)
            return deactivated
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

