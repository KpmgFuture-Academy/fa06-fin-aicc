# ai_engine/graph/nodes/waiting_agent.py

"""HUMAN_REQUIRED 플로우에서 정보 수집을 담당하는 에이전트.

동의 확인은 consent_check_node에서 룰 베이스로 처리됩니다.
이 노드는 동의 후 정보 수집만 담당합니다:
1. 대화 전체 히스토리를 분석하여 이미 언급된 정보 추출
2. 부족한 정보에 대해서만 질문 생성
3. 정보 수집 완료 시 summary_agent로 이동
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from app.core.config import settings

logger = logging.getLogger(__name__)

# LM Studio 또는 OpenAI 사용
if settings.use_lm_studio:
    llm = ChatOpenAI(
        model=settings.lm_studio_model,
        temperature=0.2,
        base_url=settings.lm_studio_base_url,
        api_key="lm-studio",
        timeout=settings.llm_timeout
    )
    logger.info(f"LM Studio 사용 - 모델: {settings.lm_studio_model}, URL: {settings.lm_studio_base_url}, 타임아웃: {settings.llm_timeout}초")
else:
    if not settings.openai_api_key:
        raise ValueError(
            "❌ OpenAI API 키가 설정되지 않았습니다!\n"
            "   .env 파일에 OPENAI_API_KEY=sk-... 를 추가해주세요.\n"
            "   프로젝트 루트 디렉토리에 .env 파일이 있는지 확인하세요."
        )
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=settings.openai_api_key,
        timeout=60
    )
    logger.info(f"✅ OpenAI API 사용 - .env 파일에서 API 키 로드")


# 수집할 필수 정보 필드 정의
REQUIRED_INFO_FIELDS = {
    "customer_name": {
        "label": "고객명",
        "question": "상담사 연결을 위해 고객님의 성함을 알려주시겠어요?",
    },
    "inquiry_type": {
        "label": "문의 유형",
        "question": "어떤 종류의 문의이신가요? (예: 카드 분실, 결제 오류, 한도 조정, 기타)",
    },
    "inquiry_detail": {
        "label": "상세 내용",
        "question": "문의하신 내용을 좀 더 자세히 말씀해 주시겠어요?",
    },
}


def _format_conversation_history(conversation_history: List[Dict]) -> str:
    """대화 히스토리를 문자열로 포맷팅합니다."""
    if not conversation_history:
        return "대화 이력 없음"
    
    formatted_lines = []
    for msg in conversation_history:
        role = msg.get("role", "unknown")
        message = msg.get("message", "")
        role_label = "고객" if role == "user" else "상담봇"
        formatted_lines.append(f"{role_label}: {message}")
    
    return "\n".join(formatted_lines)


def _extract_single_field(conversation_history: List[Dict], current_message: str, field_name: str, field_label: str) -> str | None:
    """대화에서 단일 필드 값을 추출합니다.
    
    LLM에게 JSON이 아닌 단순 텍스트로 응답받아 파싱 실패 위험을 줄입니다.
    고객(사용자) 메시지에서만 정보를 추출합니다.
    
    Args:
        conversation_history: 대화 히스토리
        current_message: 현재 사용자 메시지
        field_name: 추출할 필드명 (예: "customer_name")
        field_label: 필드 라벨 (예: "고객명")
    
    Returns:
        추출된 값 또는 None
    """
    # 고객(사용자) 메시지만 필터링 - AI 답변은 제외
    user_messages_only = [
        msg for msg in conversation_history 
        if msg.get("role") == "user"
    ]
    history_text = _format_conversation_history(user_messages_only)
    
    system_message = SystemMessage(content=f"""당신은 대화 내용에서 특정 정보를 추출하는 어시스턴트입니다.

추출할 정보: {field_label}

중요 규칙:
1. **오직 고객이 직접 말한 내용에서만** 정보를 추출하세요.
2. 상담봇/AI의 답변 내용은 절대 추출하지 마세요.
3. '{field_label}' 정보가 고객 메시지에서 명확하게 언급되었으면 그 값만 추출하세요.
4. 추측하지 마세요. 확실하지 않으면 "없음"이라고 응답하세요.
5. 추출된 값만 간단히 응답하세요. 설명이나 다른 텍스트는 포함하지 마세요.

예시:
- 고객명을 추출하는 경우: "홍길동" (O), "고객님의 이름은 홍길동입니다" (X)
- 문의 유형: "카드 분실" (O), "카드 분실 신고 접수" (X)
- 상세 내용: 고객이 말한 구체적인 상황만 (O), AI가 안내한 절차나 정보 (X)
- 정보가 없는 경우: "없음" (O)""")
    
    human_message = HumanMessage(content=f"""[고객 메시지 기록]
{history_text}

[현재 고객 메시지]
{current_message}

위 고객 메시지에서 '{field_label}' 정보를 추출해주세요. 값만 응답하세요.""")
    
    try:
        response = llm.invoke([system_message, human_message])
        extracted_value = response.content.strip()
        
        # "없음", "null", 빈 문자열 등은 None으로 처리
        if not extracted_value or extracted_value.lower() in ["없음", "null", "none", "n/a", "-"]:
            return None
        
        logger.debug(f"필드 '{field_name}' 추출 성공: {extracted_value}")
        return extracted_value
        
    except Exception as e:
        logger.error(f"필드 '{field_name}' 추출 중 오류: {str(e)}")
        return None


def _extract_info_from_conversation(conversation_history: List[Dict], current_message: str, collected_info: Dict[str, Any]) -> Dict[str, Any]:
    """대화 전체 히스토리에서 필수 정보를 한 필드씩 추출합니다.
    
    각 필드를 개별적으로 추출하여 JSON 파싱 실패 위험을 줄입니다.
    이미 수집된 필드는 건너뜁니다.
    """
    # collected_info가 None이면 빈 포맷으로 초기화
    if collected_info is None:
        collected_info = {
            "customer_name": None,
            "inquiry_type": None,
            "inquiry_detail": None
        }
    
    updated_info = collected_info.copy()
    
    # 아직 수집되지 않은 필드만 추출 시도
    for field_name, field_config in REQUIRED_INFO_FIELDS.items():
        # 이미 값이 있으면 건너뜀
        if updated_info.get(field_name):
            continue
        
        # 단일 필드 추출
        extracted_value = _extract_single_field(
            conversation_history,
            current_message,
            field_name,
            field_config["label"]
        )
        
        if extracted_value:
            updated_info[field_name] = extracted_value
            logger.info(f"필드 '{field_name}' 수집 완료: {extracted_value}")
    
    return updated_info


def _get_missing_fields(collected_info: Dict[str, Any]) -> List[str]:
    """수집되지 않은 필드 목록을 반환합니다."""
    missing = []
    for field_name in REQUIRED_INFO_FIELDS.keys():
        if field_name not in collected_info or not collected_info[field_name]:
            missing.append(field_name)
    return missing


def _generate_collection_question(missing_fields: List[str], collected_info: Dict[str, Any]) -> str:
    """부족한 정보에 대한 질문을 생성합니다."""
    if not missing_fields:
        return "필요한 정보를 모두 수집했습니다."
    
    # 첫 번째 부족한 필드에 대해 질문
    next_field = missing_fields[0]
    field_info = REQUIRED_INFO_FIELDS.get(next_field, {})
    base_question = field_info.get("question", f"{next_field}을(를) 알려주세요.")
    
    # 이미 수집된 정보가 있으면 맥락에 맞게 질문 생성
    collected_summary = ", ".join([
        f"{REQUIRED_INFO_FIELDS[k]['label']}: {v}" 
        for k, v in collected_info.items() 
        if v and k in REQUIRED_INFO_FIELDS
    ])
    
    if collected_summary:
        system_message = SystemMessage(content="""당신은 친절한 고객 상담 챗봇입니다.
상담사 연결을 위해 고객 정보를 수집하고 있습니다.
이미 수집된 정보를 참고하여 자연스럽게 다음 정보를 요청하는 문장을 생성하세요.

규칙:
1. 친절하고 공손한 어조를 유지하세요.
2. 한 번에 하나의 정보만 요청하세요.
3. 이미 수집된 정보는 다시 물어보지 마세요.
4. 1-2문장으로 간결하게 작성하세요.""")
        
        human_message = HumanMessage(content=f"""이미 수집된 정보: {collected_summary}

다음으로 수집할 정보: {field_info.get('label', next_field)}
기본 질문: {base_question}

자연스러운 질문 문장을 생성해주세요.""")
        
        try:
            response = llm.invoke([system_message, human_message])
            return response.content.strip()
        except Exception as e:
            logger.error(f"질문 생성 중 오류: {str(e)}")
            return base_question
    
    return base_question


def waiting_agent_node(state: GraphState) -> GraphState:
    """HUMAN_REQUIRED 플로우에서 정보 수집을 담당하는 노드.
    
    동의 확인은 consent_check_node에서 처리되므로,
    이 노드에 진입했다는 것은 이미 동의한 상태입니다.
    
    역할:
    1. 대화 전체 히스토리에서 필요한 정보 추출
    2. 아직 수집되지 않은 정보에 대해 질문 생성
    3. 모든 정보가 수집되면 info_collection_complete 플래그 설정
    """
    user_message = state.get("user_message", "")
    session_id = state.get("session_id", "unknown")
    conversation_history = state.get("conversation_history", [])
    
    # 수집된 정보 가져오기 (없으면 빈 딕셔너리)
    collected_info: Dict[str, Any] = state.get("collected_info", {})
    
    logger.info(f"Waiting Agent 실행 - 세션: {session_id}")
    
    try:
        # 1. 대화 전체 히스토리에서 정보 추출
        collected_info = _extract_info_from_conversation(
            conversation_history, 
            user_message, 
            collected_info
        )
        state["collected_info"] = collected_info
        
        logger.info(f"정보 추출 완료 - 세션: {session_id}, 수집된 정보: {collected_info}")
        
        # 2. 부족한 필드 확인
        missing_fields = _get_missing_fields(collected_info)
        
        # 3. 모든 정보 수집 완료 여부 확인
        if not missing_fields:
            # 모든 정보 수집 완료
            state["info_collection_complete"] = True
            state["ai_message"] = "감사합니다. 필요한 정보를 모두 수집했습니다. 잠시 후 상담사에게 연결해 드리겠습니다."
            logger.info(f"정보 수집 완료 - 세션: {session_id}, 수집된 정보: {collected_info}")
        else:
            # 부족한 정보에 대해 질문 생성
            state["info_collection_complete"] = False
            question = _generate_collection_question(missing_fields, collected_info)
            state["ai_message"] = question
            logger.info(f"정보 수집 질문 생성 - 세션: {session_id}, 부족한 필드: {missing_fields}")
        
        # 4. source_documents는 빈 리스트로 설정 (정보 수집에는 RAG 사용 안 함)
        state["source_documents"] = []
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Waiting Agent 오류 - 세션: {session_id}, 오류: {error_msg}", exc_info=True)
        
        # 에러 발생 시 기본 메시지
        state["ai_message"] = "죄송합니다. 정보 수집 중 오류가 발생했습니다. 상담사에게 연결해 드리겠습니다."
        state["info_collection_complete"] = True  # 에러 시 상담사 연결로 이동
        state["source_documents"] = []
        
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["waiting_agent_error"] = error_msg
    
    return state
