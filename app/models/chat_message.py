"""채팅 메시지 및 세션 모델"""

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class MessageRole(str, enum.Enum):
    """메시지 역할"""
    USER = "user"
    ASSISTANT = "assistant"


class ChatSession(Base):
    """채팅 세션 테이블"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Integer, default=1, nullable=False)  # 1: 활성, 0: 비활성
    
    # ========== HUMAN_REQUIRED 플로우 상태 저장 ==========
    is_human_required_flow = Column(Integer, default=0, nullable=False)  # 1: True, 0: False
    customer_consent_received = Column(Integer, default=0, nullable=False)  # 1: True, 0: False
    collected_info = Column(Text, nullable=True)  # JSON 형태로 저장 (예: {"customer_name": "홍길동"})
    info_collection_complete = Column(Integer, default=0, nullable=False)  # 1: True, 0: False
    triage_decision = Column(String(50), nullable=True)  # SIMPLE_ANSWER, AUTO_ANSWER, NEED_MORE_INFO, HUMAN_REQUIRED
    
    # 관계
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """채팅 메시지 테이블"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)
    role = Column(SQLEnum(MessageRole), nullable=False)
    message = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)  # INFO_REQ, COMPLAINT, HUMAN_REQ
    suggested_action = Column(String(50), nullable=True)  # CONTINUE, HANDOVER
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # AI 응답 관련 (선택적)
    source_documents = Column(Text, nullable=True)  # JSON 형태로 저장
    
    # 관계
    session = relationship("ChatSession", back_populates="messages")

