"""공용 프롬프트 템플릿 모음.

LangGraph 노드에서 재사용할 수 있도록 RAG 답변, 이관 요약, 감정 분석 등에
사용되는 모든 프롬프트를 한 곳에 정의한다.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Iterable, List, Optional

from app.schemas.common import IntentType
from ai_engine.graph.state import RetrievedDocument


SYSTEM_PROMPT = dedent(
    """
    당신은 대한민국 은행 상담 챗봇 어시스턴트입니다.
    항상 예의바른 존댓말을 사용하고, 고객이 요청한 정보만 정확하게 답변하세요.
    근거 문서에 없는 내용은 추측하지 말고, 상담원 연결 사유가 있다면 정중히 안내하세요.
    """
).strip()


def _format_sources(documents: Iterable[RetrievedDocument]) -> str:
    """검색된 문서를 프롬프트에 삽입할 문자열로 변환."""
    chunks: List[str] = []
    for idx, doc in enumerate(documents, start=1):
        chunk = dedent(
            f"""
            [문서 {idx}]
            출처: {doc['source']} (p.{doc['page']})
            유사도: {doc['score']:.2f}
            내용: {doc['content']}
            """
        ).strip()
        chunks.append(chunk)
    return "\n\n".join(chunks) if chunks else "관련 문서를 찾지 못했습니다."


def build_rag_prompt(
    user_message: str,
    documents: Iterable[RetrievedDocument],
    *,
    intent: Optional[IntentType] = None,
    force_handover_intent: bool = False,
    rag_low_confidence: bool = False,
    user_requested_handover: bool = False,
) -> str:
    """RAG 답변 생성을 위한 메인 프롬프트."""
    intent_hint = f"추정 의도: {intent.value}" if intent else "추정 의도: 파악 중"
    sources_block = _format_sources(documents)

    handover_flags = []
    if force_handover_intent:
        handover_flags.append("의도 분류 결과 상담원 연결 필요")
    if rag_low_confidence:
        handover_flags.append("근거 문서 유사도가 낮음")
    if user_requested_handover:
        handover_flags.append("고객이 상담원을 명시적으로 요청함")

    handover_block = (
        "### 상담원 연결 신호\n- "
        + "\n- ".join(handover_flags)
        if handover_flags
        else "### 상담원 연결 신호\n- 현재까지 특별한 신호 없음"
    )

    prompt = dedent(
        f"""
        {SYSTEM_PROMPT}

        {intent_hint}

        ### 참고 문서
        {sources_block}

        {handover_block}

        ### 고객 메시지
        {user_message}

        ### 지침
        1. 참고 문서의 내용만 기반으로 답변하세요.
        2. 근거가 부족하면 정중히 사과하고 상담원 연결을 제안하세요.
        3. 문서 출처를 답변 끝에 괄호로 간결히 표시하세요. (예: (상품설명서 p.3))
        4. 상담원 연결 신호가 하나라도 있다면, 핵심 안내 후 반드시 상담원 연결을 제안하세요.
        5. 신호가 없다면 3문장 이내로 핵심만 전달하고 추가 질문을 유도하세요.

        ### 답변
        """
    ).strip()
    return prompt


def build_handover_summary_prompt(conversation: str) -> str:
    """상담원 이관용 요약을 생성하는 프롬프트."""
    return dedent(
        f"""
        {SYSTEM_PROMPT}

        아래는 고객과 챗봇의 대화 기록입니다. 상담원에게 전달할 요약을 작성하세요.

        [대화 기록]
        {conversation}

        ### 출력 형식
        - 고객 감정 상태 (POSITIVE/NEGATIVE/NEUTRAL)
        - 3줄 요약
        - 핵심 키워드 3~5개
        - 상담원에게 꼭 알려야 할 주의사항
        """
    ).strip()


def build_sentiment_prompt(user_message: str) -> str:
    """간단한 감정 분석 프롬프트."""
    return dedent(
        f"""
        다음 고객 메시지의 감정 상태를 POSITIVE, NEGATIVE, NEUTRAL 중 하나로 판단하세요.
        판단 근거 한 줄도 같이 작성하세요.

        메시지:
        {user_message}
        """
    ).strip()

