"""Langgraph 상태 정의
FastAPI 'app/schemas'에서 선언한 데이터 계약을 그대로 충족할 수 있도록
세션/의도/답변/근거 문서 등의 필드를 한 군데에서 관리한다.

플로우차트 기반 노드 흐름:

[HUMAN_REQUIRED = FALSE 플로우 (일반 대화)]
1. 고객 채팅 Input → triage_agent
   (triage_agent 내부에서 intent_classification_tool과 rag_search_tool 사용)
2. triage_agent 분기 (triage_decision 기반):
   - SIMPLE_ANSWER → answer_agent (간단한 답변 생성) → chat_db_storage → END
   - AUTO_ANSWER → answer_agent (RAG 기반 답변 생성) → chat_db_storage → END
   - NEED_MORE_INFO → answer_agent (질문 생성) → chat_db_storage → END
   - HUMAN_REQUIRED → answer_agent (상담사 연결 안내) → chat_db_storage → END
     → is_human_required_flow=True 설정

[HUMAN_REQUIRED = TRUE 플로우 (상담사 연결)]
1. 고객 동의 확인 (customer_consent_received)
   - "네" → waiting_agent로 라우팅
   - "아니오" → is_human_required_flow=False, triage_agent로 복귀
2. waiting_agent에서 정보 수집 (대화 히스토리 기반)
   - collected_info 업데이트
   - 부족한 정보만 질문
3. 정보 수집 완료 (info_collection_complete=True)
   → summary_agent → human_transfer → END

피드백 루프:
- 각 턴마다 워크플로우가 실행되고 END로 종료됨
- 새로운 고객 채팅이 들어오면 API에서 이전 conversation_history를 포함하여
  워크플로우를 다시 실행
- conversation_history에 이전 대화를 누적하여 맥락 유지
"""

from typing import List, Optional, Dict, Any
from typing_extensions import TypedDict
from app.schemas.common import IntentType, ActionType, SentimentType, TriageDecisionType
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
    context_intent: str       # Final Classifier 모델이 분류한 문맥 의도 (38개 카테고리, 예: "결제일 안내/변경/취소", "한도 안내" 등) - 첫 번째 결과
    intent: IntentType        # 상담사 연결 필요 여부 판단을 위한 의도 타입 (INFO_REQ, COMPLAINT, HUMAN_REQ)
    intent_confidence: float  # 의도 분류 신뢰도 (0.0 ~ 1.0) - 첫 번째 결과의 confidence
    intent_classifications: Optional[List[Dict[str, Any]]]  # Top 3 의도 분류 결과 리스트 [{"intent": str, "confidence": float}, ...]
    
    # ========== 판단 에이전트 노드 (triage_agent) ==========
    triage_decision: Optional[TriageDecisionType]  # Triage 티켓 (SIMPLE_ANSWER, AUTO_ANSWER, NEED_MORE_INFO, HUMAN_REQUIRED)
    requires_consultant: bool  # 상담사 연결 필요 여부
    handover_reason: Optional[str]  # 이관 사유
    customer_intent_summary: Optional[str]  # 고객 의도 요약 (triage_agent에서 생성)
    
    # ========== RAG 검색 노드 (rag_search) ==========
    retrieved_documents: List[RetrievedDocument]  # 벡터 DB에서 검색한 문서들
    rag_best_score: Optional[float]  # 최고 유사도 점수
    rag_low_confidence: bool  # RAG 신뢰도 낮음 플래그
    
    # ========== 답변 생성 에이전트 노드 (answer_agent) ==========
    ai_message: str          # LLM이 생성한 답변
    source_documents: List[SourceDocument]  # SourceDocument 형태로 변환된 문서들
    
    # ========== HUMAN_REQUIRED 플로우 관련 ==========
    is_human_required_flow: bool  # HUMAN_REQUIRED 플로우 진입 여부
    customer_consent_received: bool  # 고객 동의 확인 여부 ("네" 응답 시 True)
    customer_declined_handover: bool  # 고객이 상담사 연결을 거부했는지 여부 ("아니오" 응답 시 True)
    collected_info: Dict[str, Any]  # 수집된 고객 정보 (예: {"customer_name": "홍길동", "inquiry_type": "카드 분실"})
    info_collection_complete: bool  # 정보 수집 완료 여부 (True 시 summary_agent로 이동)
    handover_status: Optional[str]  # 핸드오버 상태 (pending, accepted, declined, timeout)
    
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
