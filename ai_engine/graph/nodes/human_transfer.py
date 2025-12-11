# ai_engine/graph/nodes/human_transfer.py

from ai_engine.graph.state import GraphState
from app.schemas.common import ActionType
from app.schemas.handover import KMSRecommendation
from typing import Dict, Any

def consultant_transfer_node(state: GraphState) -> GraphState:
    """상담사를 연결하는 노드.
    
    summary_agent에서 생성한 요약 정보를 handover_analysis_result에 저장하고
    suggested_action을 HANDOVER로 설정합니다.
    """
    # suggested_action 설정
    state["suggested_action"] = ActionType.HANDOVER

    # 상담사 연결 안내 메시지 설정 (ChatResponse의 ai_message로 사용됨)
    # waiting_agent에서 이미 설정한 메시지가 있으면 유지
    if not state.get("ai_message"):
        state["ai_message"] = "상담사 연결이 필요하신 것으로 확인되었습니다. 곧 상담사가 연결될 예정입니다. 잠시만 기다려주세요."
    
    # summary_agent 결과를 handover_analysis_result로 변환
    summary = state.get("summary", "요약 정보가 없습니다.")
    customer_sentiment = state.get("customer_sentiment")
    extracted_keywords = state.get("extracted_keywords", [])
    kms_recommendations = state.get("kms_recommendations", [])
    
    # KMSRecommendation 리스트를 딕셔너리로 변환 (JSON 직렬화를 위해)
    kms_recommendations_dict = []
    for rec in kms_recommendations:
        if isinstance(rec, dict):
            kms_recommendations_dict.append({
                "title": rec.get("title", ""),
                "url": str(rec.get("url", "")),
                "relevance_score": rec.get("relevance_score", 0.0)
            })
        else:
            # Pydantic 모델인 경우
            if isinstance(rec, KMSRecommendation):
                kms_recommendations_dict.append({
                    "title": rec.title,
                    "url": str(rec.url),
                    "relevance_score": rec.relevance_score
                })
            else:
                # TypedDict인 경우
                kms_recommendations_dict.append({
                    "title": rec.get("title", ""),
                    "url": str(rec.get("url", "")),
                    "relevance_score": rec.get("relevance_score", 0.0)
                })
    
    handover_analysis_result: Dict[str, Any] = {
        "customer_sentiment": customer_sentiment.value if customer_sentiment else "NEUTRAL",
        "summary": summary,
        "extracted_keywords": extracted_keywords,
        "kms_recommendations": kms_recommendations_dict
    }
    
    state["handover_analysis_result"] = handover_analysis_result
    
    # TODO: 실제 상담사 연결 로직 구현 (대시보드 전송 등)
    
    return state

