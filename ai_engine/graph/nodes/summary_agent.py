# ai_engine/graph/nodes/summary_agent.py
# 요약 에이전트

from __future__ import annotations
import logging

from langchain_openai import ChatOpenAI
from ai_engine.graph.state import GraphState
from app.schemas.common import SentimentType
from app.core.config import settings

logger = logging.getLogger(__name__)

# LM Studio 또는 OpenAI 사용
if settings.use_lm_studio:
    llm = ChatOpenAI(
        model=settings.lm_studio_model,
        temperature=0.2,
        base_url=settings.lm_studio_base_url,
        api_key="lm-studio",  # LM Studio는 API 키가 필요 없지만 호환성을 위해 더미 값 사용
        timeout=settings.llm_timeout  # 타임아웃 설정 (초)
    )
    logger.info(f"LM Studio 사용 - 모델: {settings.lm_studio_model}, URL: {settings.lm_studio_base_url}, 타임아웃: {settings.llm_timeout}초")
else:
    # OpenAI API 키는 .env 파일에서만 가져옴
    if not settings.openai_api_key:
        raise ValueError(
            "❌ OpenAI API 키가 설정되지 않았습니다!\n"
            "   .env 파일에 OPENAI_API_KEY=sk-... 를 추가해주세요.\n"
            "   프로젝트 루트 디렉토리에 .env 파일이 있는지 확인하세요."
        )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=settings.openai_api_key,  # .env 파일에서만 가져옴
        timeout=60  # OpenAI는 빠르므로 60초
    )
    logger.info(f"✅ OpenAI API 사용 - .env 파일에서 API 키 로드: {settings.openai_api_key[:20]}... (길이: {len(settings.openai_api_key)} 문자)")


def summary_agent_node(state: GraphState) -> GraphState:
    """상담 내용을 요약하고 감정/키워드를 추출하는 노드"""
    conversation_history = state.get("conversation_history", [])
    
    if not conversation_history:
        # 대화 이력이 없으면 기본값 설정
        state["summary"] = None
        state["customer_sentiment"] = None
        state["extracted_keywords"] = []
        return state
    
    # 대화 이력을 문자열로 변환
    conversation_text = "\n".join([
        f"[{msg.get('role', 'unknown')}] {msg.get('message', '')}"
        for msg in conversation_history
    ])
    
    # LLM에게 요약/감정/키워드 추출 요청
    prompt = f"""다음은 고객과 챗봇의 상담 대화 기록입니다. 다음을 분석해주세요:

[대화 기록]
{conversation_text}

다음 형식으로 답변해주세요:
1. 감정 상태: POSITIVE, NEGATIVE, NEUTRAL 중 하나
2. 요약 (3줄):
   - 첫 번째 줄
   - 두 번째 줄
   - 세 번째 줄
3. 핵심 키워드: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5

답변:"""
    
    try:
        logger.info(f"요약 에이전트 실행 - 세션: {state.get('session_id', 'unknown')}")
        response = llm.invoke(prompt).content
        logger.debug(f"요약 에이전트 응답 - 세션: {state.get('session_id', 'unknown')}, 응답 길이: {len(response)}")
        
        # 응답 파싱
        lines = response.strip().split('\n')
        
        # 감정 상태 추출
        sentiment = None
        for line in lines:
            if '감정 상태' in line or '감정' in line:
                if 'POSITIVE' in line.upper():
                    sentiment = SentimentType.POSITIVE
                elif 'NEGATIVE' in line.upper():
                    sentiment = SentimentType.NEGATIVE
                elif 'NEUTRAL' in line.upper():
                    sentiment = SentimentType.NEUTRAL
                break
        
        # 요약 추출 (3줄)
        summary_lines = []
        in_summary = False
        for line in lines:
            if '요약' in line or '1.' in line or '- 첫' in line:
                in_summary = True
                continue
            if in_summary and (line.strip().startswith('-') or line.strip().startswith('•')):
                summary_lines.append(line.strip().lstrip('- ').lstrip('• '))
            elif in_summary and line.strip() and len(summary_lines) < 3:
                if not any(keyword in line for keyword in ['핵심', '키워드', '3.', '2.']):
                    summary_lines.append(line.strip())
            if len(summary_lines) >= 3:
                break
        
        summary = "\n".join(summary_lines) if summary_lines else None
        
        # 키워드 추출
        keywords = []
        in_keywords = False
        for line in lines:
            if '핵심 키워드' in line or '키워드' in line:
                in_keywords = True
                # 같은 줄에서 키워드 추출
                if ':' in line:
                    keyword_part = line.split(':', 1)[1].strip()
                    keywords.extend([k.strip() for k in keyword_part.split(',') if k.strip()])
                continue
            if in_keywords:
                if ',' in line:
                    keywords.extend([k.strip() for k in line.split(',') if k.strip()])
                elif line.strip() and not any(skip in line for skip in ['답변', '---', '===']):
                    keywords.append(line.strip())
                if len(keywords) >= 5:
                    break
        
        # 상태 업데이트
        state["summary"] = summary
        state["customer_sentiment"] = sentiment
        state["extracted_keywords"] = keywords[:5]  # 최대 5개
        
    except Exception as e:
        # 에러 발생 시 기본값 설정
        error_msg = str(e)
        logger.error(f"요약 에이전트 오류 - 세션: {state.get('session_id', 'unknown')}, 오류: {error_msg}", exc_info=True)
        state["summary"] = None
        state["customer_sentiment"] = None
        state["extracted_keywords"] = []
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["summary_error"] = error_msg
    
    return state

