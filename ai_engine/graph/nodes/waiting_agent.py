# ai_engine/graph/nodes/waiting_agent.py

"""HUMAN_REQUIRED 플로우에서 정보 수집을 담당하는 에이전트.

동의 확인은 consent_check_node에서 룰 베이스로 처리됩니다.
이 노드는 동의 후 정보 수집만 담당합니다:
1. triage_agent에서 분류한 카테고리(context_intent)를 기반으로 필요한 슬롯 결정
2. 대화 히스토리에서 이미 언급된 정보 추출
3. 부족한 정보에 대해서만 질문 생성
4. 정보 수집 완료 시 summary_agent로 이동

도메인별 슬롯 시스템:
- slot_definitions.json: 카테고리별 필수/선택 슬롯 정의
- slot_metadata.json: 슬롯별 라벨, 질문, 검증 규칙
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from ai_engine.graph.state import GraphState
from ai_engine.graph.utils.slot_loader import get_slot_loader
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
- 카드 뒤 4자리: "1234" (O), "카드번호 뒤 4자리는 1234입니다" (X)
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


def _extract_info_from_conversation(
    conversation_history: List[Dict],
    current_message: str,
    collected_info: Dict[str, Any],
    required_slots: List[str],
    slot_loader
) -> Dict[str, Any]:
    """대화 전체 히스토리에서 필요한 슬롯 정보를 추출합니다.

    각 슬롯을 개별적으로 추출하여 JSON 파싱 실패 위험을 줄입니다.
    이미 수집된 슬롯은 건너뜁니다.
    """
    if collected_info is None:
        collected_info = {}

    updated_info = collected_info.copy()

    # 아직 수집되지 않은 슬롯만 추출 시도
    for slot_name in required_slots:
        # 이미 값이 있으면 건너뜀
        if updated_info.get(slot_name):
            continue

        # 슬롯 라벨 가져오기
        slot_label = slot_loader.get_slot_label(slot_name)

        # 단일 슬롯 추출
        extracted_value = _extract_single_field(
            conversation_history,
            current_message,
            slot_name,
            slot_label
        )

        if extracted_value:
            updated_info[slot_name] = extracted_value
            logger.info(f"슬롯 '{slot_name}' 수집 완료: {extracted_value}")

    return updated_info


def _generate_collection_question(
    missing_slots: List[str],
    collected_info: Dict[str, Any],
    slot_loader
) -> str:
    """부족한 슬롯에 대한 질문을 생성합니다."""
    if not missing_slots:
        return "필요한 정보를 모두 수집했습니다."

    # 첫 번째 부족한 슬롯에 대해 질문
    next_slot = missing_slots[0]
    base_question = slot_loader.get_slot_question(next_slot)
    slot_label = slot_loader.get_slot_label(next_slot)

    # 이미 수집된 정보가 있으면 맥락에 맞게 질문 생성
    collected_labels = []
    for k, v in collected_info.items():
        if v and not k.startswith("_"):  # 내부 필드(_로 시작)는 제외
            label = slot_loader.get_slot_label(k)
            collected_labels.append(f"{label}: {v}")

    collected_summary = ", ".join(collected_labels)

    if collected_summary:
        system_message = SystemMessage(content="""당신은 친절한 고객 상담 챗봇입니다.
상담사 연결을 위해 고객 정보를 수집하고 있습니다.
이미 수집된 정보를 참고하여 자연스럽게 다음 정보를 요청하는 문장을 생성하세요.

규칙:
1. 친절하고 공손한 어조를 유지하세요.
2. 한 번에 하나의 정보만 요청하세요.
3. 이미 수집된 정보는 다시 물어보지 마세요.
4. 1-2문장으로 간결하게 작성하세요.
5. "감사합니다"로 시작하세요.""")

        human_message = HumanMessage(content=f"""이미 수집된 정보: {collected_summary}

다음으로 수집할 정보: {slot_label}
기본 질문: {base_question}

자연스러운 질문 문장을 생성해주세요.""")

        try:
            response = llm.invoke([system_message, human_message])
            return response.content.strip()
        except Exception as e:
            logger.error(f"질문 생성 중 오류: {str(e)}")
            return base_question

    return base_question


def _determine_category(state: GraphState) -> str:
    """상태에서 카테고리를 결정합니다.

    우선순위:
    1. context_intent (triage_agent에서 분류한 38개 카테고리)
    2. collected_info.inquiry_detail (기존 방식 호환)
    3. 기본값: "기타 문의"
    """
    # 1. context_intent 확인 (38개 카테고리)
    context_intent = state.get("context_intent")
    if context_intent and context_intent != "기타":
        return context_intent

    # 2. collected_info에서 확인
    collected_info = state.get("collected_info", {})
    inquiry_detail = collected_info.get("inquiry_detail")
    if inquiry_detail:
        return inquiry_detail

    # 3. 기본값
    return "기타 문의"


def waiting_agent_node(state: GraphState) -> GraphState:
    """HUMAN_REQUIRED 플로우에서 정보 수집을 담당하는 노드.

    동의 확인은 consent_check_node에서 처리되므로,
    이 노드에 진입했다는 것은 이미 동의한 상태입니다.

    역할:
    1. 카테고리(context_intent)에 따른 필수 슬롯 결정
    2. 대화 전체 히스토리에서 필요한 정보 추출
    3. 아직 수집되지 않은 정보에 대해 질문 생성
    4. 모든 필수 슬롯 수집 완료 시 info_collection_complete 플래그 설정
    """
    user_message = state.get("user_message", "")
    session_id = state.get("session_id", "unknown")
    conversation_history = state.get("conversation_history", [])

    # 수집된 정보 가져오기 (없으면 빈 딕셔너리)
    collected_info: Dict[str, Any] = state.get("collected_info", {})

    logger.info(f"Waiting Agent 실행 - 세션: {session_id}")

    try:
        # 슬롯 로더 가져오기
        slot_loader = get_slot_loader()

        # 1. 카테고리 결정
        category = _determine_category(state)
        logger.info(f"카테고리 결정: {category}")

        # 도메인 정보 저장 (UI 표시용)
        domain_code = slot_loader.get_domain_by_category(category)
        domain_name = slot_loader.get_domain_name(domain_code) if domain_code else "기타"

        # collected_info에 도메인/카테고리 정보 저장
        collected_info["_domain_code"] = domain_code or "_DEFAULT"
        collected_info["_domain_name"] = domain_name
        collected_info["_category"] = category

        # 기존 호환성을 위해 inquiry_type, inquiry_detail도 설정
        if not collected_info.get("inquiry_type"):
            collected_info["inquiry_type"] = domain_name
        if not collected_info.get("inquiry_detail"):
            collected_info["inquiry_detail"] = category

        # 2. 필수 슬롯 결정
        required_slots, optional_slots = slot_loader.get_slots_for_category(category)
        logger.info(f"필수 슬롯: {required_slots}, 선택 슬롯: {optional_slots}")

        # 3. 대화 히스토리에서 정보 추출
        collected_info = _extract_info_from_conversation(
            conversation_history,
            user_message,
            collected_info,
            required_slots,
            slot_loader
        )
        state["collected_info"] = collected_info

        logger.info(f"정보 추출 완료 - 세션: {session_id}, 수집된 정보: {collected_info}")

        # 4. 부족한 슬롯 확인
        missing_slots = slot_loader.get_missing_required_slots(category, collected_info)

        # 5. 모든 정보 수집 완료 여부 확인
        if not missing_slots:
            # 모든 정보 수집 완료
            state["info_collection_complete"] = True
            state["ai_message"] = "감사합니다. 필요한 정보를 모두 수집했습니다. 잠시 후 상담사에게 연결해 드리겠습니다."
            logger.info(f"정보 수집 완료 - 세션: {session_id}, 수집된 정보: {collected_info}")
        else:
            # 부족한 정보에 대해 질문 생성
            state["info_collection_complete"] = False
            question = _generate_collection_question(missing_slots, collected_info, slot_loader)
            state["ai_message"] = question
            logger.info(f"정보 수집 질문 생성 - 세션: {session_id}, 부족한 슬롯: {missing_slots}")

        # 6. source_documents는 빈 리스트로 설정 (정보 수집에는 RAG 사용 안 함)
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
