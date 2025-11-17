# 채팅 담당 직원 - 진짜 뇌(Langgraph)를 추후 연결해야 함

from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse, SourceDocument
from app.schemas.common import IntentType, ActionType

router = APIRouter()

@router.post("/message", response_model=ChatResponse)
async def chat_message(request: ChatRequest):
    # [Mock Logic] 무조건 이 답변만 나갑니다.
    return ChatResponse(
        ai_message=f"네, 고객님. 말씀하신 '{request.user_message}'에 대해 확인해 보겠습니다. (테스트 중)",
        intent=IntentType.INFO_REQ,
        suggested_action=ActionType.CONTINUE,
        source_documents=[
            SourceDocument(source="상품설명서.pdf", page=1, score=0.99)
        ]
    )