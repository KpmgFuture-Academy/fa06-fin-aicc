"""채팅 히스토리 Tool: 대화 이력을 포맷팅하여 LLM에 제공합니다."""

from __future__ import annotations

import logging
from typing import List, Optional
from langchain_core.tools import tool
from ai_engine.graph.state import ConversationMessage

logger = logging.getLogger(__name__)


@tool
def format_chat_history(
    conversation_history: List[ConversationMessage],
    max_messages: int = 10,
    include_timestamps: bool = False
) -> str:
    """대화 이력을 포맷팅하여 LLM이 읽기 쉬운 문자열로 반환합니다.
    
    Args:
        conversation_history: 대화 이력 리스트 (ConversationMessage 리스트)
        max_messages: 포함할 최대 메시지 수 (최근 N개만 포함, 기본값: 10)
        include_timestamps: 타임스탬프 포함 여부 (기본값: False)
        
    Returns:
        포맷팅된 대화 이력 문자열. 형식:
        ```
        [대화 이력]
        사용자: 첫 번째 사용자 메시지
        어시스턴트: 첫 번째 어시스턴트 응답
        사용자: 두 번째 사용자 메시지
        ...
        ```
        
        대화 이력이 없으면 "대화 이력이 없습니다." 반환
        
    Examples:
        format_chat_history([...], max_messages=5) -> "[대화 이력]\n사용자: ...\n어시스턴트: ..."
        format_chat_history([]) -> "대화 이력이 없습니다."
    """
    try:
        # 대화 이력이 없으면 빈 문자열 반환
        if not conversation_history:
            logger.debug("대화 이력이 없습니다.")
            return "대화 이력이 없습니다."
        
        # 최근 N개 메시지만 선택 (최신 메시지부터)
        recent_messages = conversation_history[-max_messages:] if len(conversation_history) > max_messages else conversation_history
        
        # 포맷팅된 문자열 생성
        formatted_lines = ["[대화 이력]"]
        
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            message = msg.get("message", "")
            timestamp = msg.get("timestamp")
            
            # role을 한글로 변환
            if role == "user":
                role_label = "사용자"
            elif role == "assistant":
                role_label = "어시스턴트"
            else:
                role_label = role
            
            # 메시지 포맷팅
            if include_timestamps and timestamp:
                formatted_lines.append(f"{role_label} ({timestamp}): {message}")
            else:
                formatted_lines.append(f"{role_label}: {message}")
        
        # 전체 메시지 수가 max_messages보다 많으면 안내 추가
        if len(conversation_history) > max_messages:
            formatted_lines.append(f"\n(총 {len(conversation_history)}개 메시지 중 최근 {max_messages}개만 표시)")
        
        result = "\n".join(formatted_lines)
        
        logger.info(f"대화 이력 포맷팅 완료: 총 {len(conversation_history)}개 중 {len(recent_messages)}개 포함")
        return result
        
    except Exception as e:
        # 에러 발생 시 로깅 및 fallback
        logger.error(f"대화 이력 포맷팅 실패: {str(e)}", exc_info=True)
        return "대화 이력 포맷팅 중 오류가 발생했습니다."


@tool
def get_recent_user_messages(
    conversation_history: List[ConversationMessage],
    count: int = 3
) -> str:
    """최근 사용자 메시지만 추출하여 반환합니다.
    
    Args:
        conversation_history: 대화 이력 리스트
        count: 추출할 최근 사용자 메시지 수 (기본값: 3)
        
    Returns:
        최근 사용자 메시지들을 포맷팅한 문자열
        
    Examples:
        get_recent_user_messages([...], count=3) -> "[최근 사용자 메시지]\n1. ...\n2. ...\n3. ..."
    """
    try:
        if not conversation_history:
            return "사용자 메시지가 없습니다."
        
        # 사용자 메시지만 필터링
        user_messages = [
            msg.get("message", "") 
            for msg in conversation_history 
            if msg.get("role") == "user"
        ]
        
        # 최근 N개만 선택
        recent_user_messages = user_messages[-count:] if len(user_messages) > count else user_messages
        
        if not recent_user_messages:
            return "사용자 메시지가 없습니다."
        
        # 포맷팅
        formatted_lines = ["[최근 사용자 메시지]"]
        for i, msg in enumerate(recent_user_messages, 1):
            formatted_lines.append(f"{i}. {msg}")
        
        result = "\n".join(formatted_lines)
        logger.debug(f"최근 사용자 메시지 추출: {len(recent_user_messages)}개")
        return result
        
    except Exception as e:
        logger.error(f"최근 사용자 메시지 추출 실패: {str(e)}", exc_info=True)
        return "사용자 메시지 추출 중 오류가 발생했습니다."


@tool
def summarize_conversation_context(
    conversation_history: List[ConversationMessage],
    max_length: int = 500
) -> str:
    """대화 이력을 간단히 요약하여 반환합니다.
    
    주로 토큰 제한이 있을 때 사용합니다.
    
    Args:
        conversation_history: 대화 이력 리스트
        max_length: 최대 문자열 길이 (기본값: 500)
        
    Returns:
        요약된 대화 맥락 문자열
    """
    try:
        if not conversation_history:
            return "대화 이력이 없습니다."
        
        # 간단한 요약: 메시지 수와 주요 키워드
        user_messages = [msg.get("message", "") for msg in conversation_history if msg.get("role") == "user"]
        assistant_messages = [msg.get("message", "") for msg in conversation_history if msg.get("role") == "assistant"]
        
        summary_parts = [
            f"[대화 맥락 요약]",
            f"총 대화 턴 수: {len(user_messages)}",
            f"최근 사용자 메시지: {user_messages[-1] if user_messages else '없음'}"
        ]
        
        result = "\n".join(summary_parts)
        
        # 길이 제한
        if len(result) > max_length:
            result = result[:max_length] + "..."
        
        logger.debug(f"대화 맥락 요약 생성: {len(conversation_history)}개 메시지")
        return result
        
    except Exception as e:
        logger.error(f"대화 맥락 요약 실패: {str(e)}", exc_info=True)
        return "대화 맥락 요약 중 오류가 발생했습니다."


# Tool 인스턴스 생성 (주로 사용할 메인 툴)
chat_history_tool = format_chat_history

