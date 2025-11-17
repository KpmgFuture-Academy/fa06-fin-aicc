from fastapi import APIRouter
import asyncio
from app.schemas.handover import HandoverRequest, HandoverResponse, AnalysisResult, KMSRecommendation
from app.schemas.common import SentimentType

router = APIRouter()

@router.post("/analyze", response_model=HandoverResponse)
async def analyze_handover(request: HandoverRequest):
    # 분석하는 척 2초 딜레이
    await asyncio.sleep(2)

    # 프론트엔드 개발용 가짜 데이터 반환
    return HandoverResponse(
        status="success",
        analysis_result=AnalysisResult(
            customer_sentiment=SentimentType.NEGATIVE,
            summary="고객은 주택담보대출 중도상환수수료 면제 조건을 문의했으나, 챗봇 답변이 불충분하여 상담을 요청함.",
            extracted_keywords=["중도상환수수료", "면제 조건", "주택담보대출"],
            kms_recommendations=[
                KMSRecommendation(
                    title="2025년 중도상환수수료 면제 규정",
                    url="http://bank-kms.com/doc/12345",
                    relevance_score=0.98
                ),
                KMSRecommendation(
                    title="대출 상환 관련 FAQ",
                    url="http://bank-kms.com/doc/67890",
                    relevance_score=0.85
                )
            ]
        )
    )