from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.common import IntentType, ActionType

class ChatRequest(BaseModel):
    session_id: str = Field(..., example="sess_001")
    user_message: str = Field(..., example="대출 금리 얼마야?")

class SourceDocument(BaseModel):
    source: str
    page: int
    score: float

class ChatResponse(BaseModel):
    ai_message: str
    intent: IntentType
    suggested_action: ActionType
    source_documents: List[SourceDocument] = []