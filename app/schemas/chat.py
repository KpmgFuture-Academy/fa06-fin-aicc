# 챗봇과 대화할 때 주고받는 데이터 포맷

from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.common import IntentType, ActionType

# 요청: '세션ID랑 질문을 꼭 적어서 보내'라고 강제
class ChatRequest(BaseModel):
    session_id: str = Field(..., example="sess_001")
    user_message: str = Field(..., example="대출 금리 얼마야?")

class SourceDocument(BaseModel):
    source: str
    page: int
    score: float

# 응답: '답변 줄 때는 AI 메시지랑 근거 문서를 담아서 줄게'라는 약속
class ChatResponse(BaseModel):
    ai_message: str
    intent: IntentType
    suggested_action: ActionType
    source_documents: List[SourceDocument] = []
    # 정보 수집 완료 여부 (True일 때만 상담원 연결 모드 활성화)
    info_collection_complete: bool = False