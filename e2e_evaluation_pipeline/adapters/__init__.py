# e2e_evaluation_pipeline/adapters/__init__.py
"""실제 시스템 연동 어댑터.

E2E 평가 파이프라인에서 실제 AI 엔진 모듈들과 연동하기 위한 어댑터 모음.

사용 예시:
    from e2e_evaluation_pipeline.adapters import (
        LangGraphAdapter,
        IntentAdapter,
        RAGAdapter,
        SlotAdapter,
        FlowAdapter
    )

    # Intent 분류 테스트
    intent_adapter = IntentAdapter()
    result = intent_adapter.classify("카드 분실했어요")
    print(result.predicted_intent)  # "분실/도난 신고"

    # RAG 검색 테스트
    rag_adapter = RAGAdapter()
    result = rag_adapter.search("결제일 변경하려면 어떻게 해야 하나요?")
    print(result.documents)

    # 슬롯 추출 테스트
    slot_adapter = SlotAdapter()
    result = slot_adapter.extract_slots([], "카드 뒤 4자리는 1234입니다", "분실/도난 신고")
    print(result.extracted_slots)  # {"card_last_4_digits": "1234"}

    # 전체 워크플로우 테스트
    langgraph_adapter = LangGraphAdapter()
    result = langgraph_adapter.execute("결제일 변경하고 싶어요")
    print(result.ai_message)
"""

from .langgraph_adapter import LangGraphAdapter, WorkflowExecutionResult
from .intent_adapter import IntentAdapter, IntentClassificationResult
from .rag_adapter import RAGAdapter, RAGSearchResult, RetrievedDocument
from .slot_adapter import SlotAdapter, SlotExtractionResult, SlotDefinition
from .flow_adapter import FlowAdapter, FlowExecutionResult, FlowType

__all__ = [
    # 어댑터 클래스
    "LangGraphAdapter",
    "IntentAdapter",
    "RAGAdapter",
    "SlotAdapter",
    "FlowAdapter",
    # 결과 클래스
    "WorkflowExecutionResult",
    "IntentClassificationResult",
    "RAGSearchResult",
    "RetrievedDocument",
    "SlotExtractionResult",
    "SlotDefinition",
    "FlowExecutionResult",
    "FlowType"
]
