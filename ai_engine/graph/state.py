# ai_engine/graph/state.py
# 세션 정보, 사용자 메시지, 의도, 검색 결과, LLM 답변 등 상태 관리

"""Langgraph 상태 정의
FastAPI 'app/schemas'에서 선언한 데이터 계약을 그대로 충족할 수 있도록
세션/의도/답변/근거 문서 등의 필드를 한 군데에서 관리한다.
"""

from typing import TypedDict, List, Optional
from app.schemas.common import IntentType, ActionType
from app.schemas.chat import SourceDocument


class RetrievedDocument(TypedDict):
    """RAG 검색 결과 문서 (내부 처리용)"""
    content: str  # 문서 내용
    source: str   # 문서 출처 (파일명 등)
    page: int     # 페이지 번호
    score: float  # 유사도 점수


class GraphState(TypedDict, total=False):
    """LangGraph 워크플로우에서 사용하는 상태 객체
    
    노드 간에 주고받는 모든 정보를 담는 컨테이너.
    최종적으로 ChatResponse로 변환되어 API 응답으로 반환된다.
    """
    
    # 입력 (ChatRequest에서 받음)
    session_id: str           # 세션 ID
    user_message: str         # 사용자 메시지
    
    # 의도 분류 결과
    intent: IntentType        # KoBERT 모델이 분류한 의도
    
    # RAG 검색 결과 (LangGraph 내부에서 쓰는 원본 검색 결과)
    retrieved_documents: List[RetrievedDocument]  # 벡터 DB에서 검색한 문서들
    
    # LLM 답변 생성 결과
    ai_message: str          # LLM이 생성한 답변
    
    # 이관 판단 결과
    suggested_action: ActionType  # CONTINUE 또는 HANDOVER
    
    # 최종 응답용 (ChatResponse로 변환 시 사용)
    source_documents: List[SourceDocument]  # SourceDocument 형태로 변환된 문서들
    
    # 선택적 필드 (향후 확장용)
    conversation_history: Optional[List[dict]]  # 이전 대화 이력 (DB에서 가져올 수 있음)
    error_message: Optional[str]  # 에러 발생 시 메시지
