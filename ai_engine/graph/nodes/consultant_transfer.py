# ai_engine/graph/nodes/human_transfer.py

from __future__ import annotations

from ai_engine.graph.state import GraphState
from app.schemas.common import ActionType

def consultant_transfer_node(state: GraphState) -> GraphState:
    """상담사를 연결하고 대시보드 데이터를 준비하는 노드.
    
    summary_agent에서 생성된 요약 정보를 받아서 handover_analysis_result로 가공하여
    상담사 대시보드에 표시할 데이터를 준비합니다.
    """
    # suggested_action을 HANDOVER로 설정
    state["suggested_action"] = ActionType.HANDOVER
    
    # summary_agent에서 생성된 정보 가져오기
    summary = state.get("summary")
    customer_sentiment = state.get("customer_sentiment")
    extracted_keywords = state.get("extracted_keywords", [])
    kms_recommendations = state.get("kms_recommendations", [])
    
    # handover_analysis_result 구성
    # AnalysisResult 구조에 맞게 딕셔너리로 구성
    analysis_result = {
        "customer_sentiment": customer_sentiment.value if customer_sentiment else "NEUTRAL",
        "summary": summary if summary else "요약 정보가 없습니다.",
        "extracted_keywords": extracted_keywords,
        "kms_recommendations": [
            {
                "title": rec.get("title", ""),
                "url": rec.get("url", ""),
                "relevance_score": rec.get("relevance_score", 0.0)
            }
            for rec in kms_recommendations
        ] if kms_recommendations else []
    }
    
    state["handover_analysis_result"] = analysis_result
    
    # TODO: 실제 상담사 연결 로직 구현
    # - 상담사 대기열에 추가
    # - 상담사에게 알림 전송
    # - 세션 상태 업데이트 등
    
    return state

