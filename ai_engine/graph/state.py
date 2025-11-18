"""Langgraph 상태 정의
FastAPI 'app/schemas'에서 선언한 데이터 계약을 그대로 충족할 수 있도록
세션/의도/답변/근거 문서 등의 필드를 한 군데에서 관리한다.

플로우차트 기반 노드 흐름:
1. 고객 채팅 Input → intent_classification
2. intent_classification → decision_agent
3. decision_agent 분기:
   1) 상담사 연결 필요 → summary_agent → human_transfer → END (대시보드)
   2) 챗봇으로 처리 가능 → rag_search → answer_agent → chat_db_storage → END

피드백 루프:
- 각 턴마다 워크플로우가 실행되고 END로 종료됨
- 새로운 고객 채팅이 들어오면 API에서 이전 conversation_history를 포함하여
  다시 intent_classification부터 워크플로우를 실행
- conversation_history에 이전 대화를 누적하여 맥락 유지
- 상담사 이관이 결정된 시점에만 summary_agent가 실행되어 전체 대화 요약 생성
"""

from typing import TypedDict, List, Optional, Dict, Any
from app.schemas.common import IntentType, ActionType, SentimentType
from app.schemas.chat import SourceDocument
from app.schemas.handover import KMSRecommendation


class RetrievedDocument(TypedDict):
    """RAG 검색 결과 문서 (내부 처리용)"""
    content: str  # 문서 내용
    source: str   # 문서 출처 (파일명 등)
    page: int     # 페이지 번호
    score: float  # 유사도 점수


class ConversationMessage(TypedDict):
    """대화 메시지 단위"""
    role: str  # "user" 또는 "assistant"
    message: str  # 메시지 내용
    timestamp: Optional[str]  # 타임스탬프


class GraphState(TypedDict, total=False):
    """LangGraph 워크플로우에서 사용하는 상태 객체
    
    노드 간에 주고받는 모든 정보를 담는 컨테이너.
    최종적으로 ChatResponse 또는 HandoverResponse로 변환되어 API 응답으로 반환된다.
    """
    
    # ========== 입력 (ChatRequest에서 받음) ==========
    session_id: str           # 세션 ID (피드백 루프에서 동일 세션 유지)
    user_message: str         # 사용자 메시지 (현재 턴의 메시지)
    
    # ========== 피드백 루프 관련 ==========
    # 새로운 채팅이 들어올 때 이전 대화 맥락을 유지하기 위한 필드들
    previous_turn_state: Optional[Dict[str, Any]]  # 이전 턴의 주요 상태 정보 (선택적)
    
    # ========== 의도 분류 노드 (intent_classification) ==========
    intent: IntentType        # KoBERT 모델이 분류한 의도
    intent_confidence: float  # 의도 분류 신뢰도 (0.0 ~ 1.0)
    
    # ========== 판단 에이전트 노드 (decision_agent) ==========
    requires_consultant: bool  # 상담사 연결 필요 여부
    handover_reason: Optional[str]  # 이관 사유
    
    # ========== RAG 검색 노드 (rag_search) ==========
    retrieved_documents: List[RetrievedDocument]  # 벡터 DB에서 검색한 문서들
    rag_best_score: Optional[float]  # 최고 유사도 점수
    rag_low_confidence: bool  # RAG 신뢰도 낮음 플래그
    
    # ========== 답변 생성 에이전트 노드 (answer_agent) ==========
    ai_message: str          # LLM이 생성한 답변
    source_documents: List[SourceDocument]  # SourceDocument 형태로 변환된 문서들
    
    # ========== 상담 DB 저장 노드 (chat_db_storage) ==========
    # DB 저장은 별도 처리, 상태는 그대로 유지
    db_stored: bool  # DB 저장 완료 여부
    is_session_end: bool  # 세션 종료 여부 (현재는 사용되지 않음, 향후 확장용)
    
    # ========== 요약 에이전트 노드 (summary_agent) ==========
    conversation_history: List[ConversationMessage]  # 전체 대화 이력
    summary: Optional[str]  # 상담 요약 (3줄)
    customer_sentiment: Optional[SentimentType]  # 고객 감정 상태
    extracted_keywords: List[str]  # 핵심 키워드 리스트
    
    # ========== KMS 문서 검색 에이전트 노드 (kms_document_search_agent) ==========
    kms_recommendations: List[KMSRecommendation]  # 추천 KMS 문서 리스트
    
    # ========== 상담사 이관 노드 (human_transfer) ==========
    suggested_action: ActionType  # CONTINUE 또는 HANDOVER
    handover_analysis_result: Optional[Dict[str, Any]]  # HandoverResponse의 analysis_result
    
    # ========== 공통 메타데이터 ==========
    metadata: Dict[str, Any]  # 추가 메타데이터 (플래그, 오류 정보 등)
    error_message: Optional[str]  # 에러 발생 시 메시지
    
    # ========== 선택적 필드 ==========
    conversation_turn: int  # 대화 턴 수 (피드백 루프마다 증가)
    processing_start_time: Optional[str]  # 처리 시작 시간
    processing_end_time: Optional[str]  # 처리 종료 시간
    is_new_turn: bool  # 새로운 턴 시작 여부 (피드백 루프 감지용)
