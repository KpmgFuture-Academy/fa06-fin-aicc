# 상담원 이관 시 챗봇의 상세 리포트 양식

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from app.schemas.common import SentimentType

# 1. 요청 모델
class HandoverRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    trigger_reason: str = Field(..., description="이관 사유", example="USER_REQUEST")

# 2. 하위 모델: 추천 KMS 링크
class KMSRecommendation(BaseModel):
    title: str = Field(..., description="문서 제목")
    url: HttpUrl = Field(..., description="문서 링크 URL")
    relevance_score: float = Field(..., description="관련도")

# 3. 하위 모델: 분석 결과 본문
class AnalysisResult(BaseModel):
    customer_sentiment: SentimentType = Field(..., description="고객 감정 상태")
    summary: str = Field(..., description="3줄 요약")
    extracted_keywords: List[str] = Field(..., description="핵심 키워드 리스트")
    kms_recommendations: List[KMSRecommendation] = Field(..., description="추천 문서 리스트")

# 4. 응답 모델
class HandoverResponse(BaseModel):
    status: str = Field("success", description="처리 상태")
    analysis_result: AnalysisResult