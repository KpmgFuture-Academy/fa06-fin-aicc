import streamlit as st
import requests
import uuid
import time
import os

# --- 백엔드 설정 ---
BACKEND_URL = os.getenv("BACKEND_URL", "mock")  # 기본은 목 모드


def _is_mock_mode():
    return BACKEND_URL.lower() == "mock"


def _mock_chat_response(payload):
    user_message = payload.get("user_message", "")
    return {
        "ai_message": f"(Mock) '{user_message}' 문의를 확인했습니다.",
        "source_documents": [
            {"source": "FAQ.pdf", "page": 1, "score": 0.95},
            {"source": "약관집.pdf", "page": 3, "score": 0.88},
        ],
    }


def _mock_handover_response(_payload):
    return {
        "status": "success",
        "analysis_result": {
            "customer_sentiment": "POSITIVE",
            "summary": "상담원 연결 요청 이전에 모의 응답으로 진행되었습니다.",
            "extracted_keywords": ["모의", "상담원 연결", "테스트"],
            "kms_recommendations": [
                {
                    "title": "Mock 상품 안내서",
                    "url": "http://example.com/mock-guide",
                    "relevance_score": 0.91,
                }
            ],
        },
    }


def call_backend(path: str, payload: dict):
    if _is_mock_mode():
        if path == "/api/v1/chat/message":
            return _mock_chat_response(payload)
        if path == "/api/v1/handover/analyze":
            return _mock_handover_response(payload)
        raise ValueError(f"Mock mode does not support path: {path}")

    response = requests.post(
        f"{BACKEND_URL}{path}",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

# --- 페이지 설정 ---
st.set_page_config(
    page_title="AICC MVP 고객용 챗봇 (사전 상담)",
    layout="wide"
)

st.title("🤖 AICC MVP 고객용 챗봇")
st.caption("콜센터 연결 전, 문의 내용 사전 정리")

# --- 세션 ID 및 대화 기록 초기화 ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.chatbot_messages = [
        {"role": "assistant", "content": "안녕하세요. 은행 AI 챗봇입니다. 무엇을 도와드릴까요?"}
    ]

# --- 대화 기록 표시 ---
for message in st.session_state.chatbot_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # 답변에 근거 문서가 있는 경우 함께 표시
        if "sources" in message and message["sources"]:
            with st.expander("참고 자료"):
                for source in message["sources"]:
                    st.info(f"문서: {source['source']} (페이지: {source['page']}, 관련도: {source['score']:.2f})")

# --- 새로운 입력 처리 및 백엔드 API 호출 ---
if prompt := st.chat_input("문의 내용을 입력해 주세요."):
    
    # 고객 입력 추가 및 표시
    st.session_state.chatbot_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 백엔드 API로 챗봇 응답 요청
    with st.chat_message("assistant"):
        with st.spinner("AI 챗봇이 답변을 생성하는 중..."):
            try:
                api_response = call_backend(
                    "/api/v1/chat/message",
                    {"session_id": st.session_state.session_id, "user_message": prompt},
                )
                ai_message = api_response.get("ai_message", "죄송합니다. 답변을 생성하지 못했습니다.")
                source_documents = api_response.get("source_documents", [])
                
                st.markdown(ai_message)
                
                # 답변 및 근거 자료를 세션에 저장
                st.session_state.chatbot_messages.append({
                    "role": "assistant", 
                    "content": ai_message,
                    "sources": source_documents # 근거 자료 저장
                })

                # 근거 자료가 있으면 함께 표시
                if source_documents:
                    with st.expander("참고 자료"):
                        for source in source_documents:
                            st.info(f"문서: {source['source']} (페이지: {source['page']}, 관련도: {source['score']:.2f})")

            except requests.exceptions.RequestException as e:
                st.error(f"🚨 API 요청 오류: {e}")
            except Exception as e:
                st.error(f"🚨 처리 중 오류 발생: {e}")


# --- 대화 종료 및 상담원 연결 로직 ---
st.markdown("---")

if st.button("전문 상담원 연결 요청"):
    with st.spinner("대화 내용을 분석하여 상담원에게 전달하는 중입니다..."):
        try:
            # 1. 백엔드에 분석 요청
            analysis_data = call_backend(
                "/api/v1/handover/analyze",
                {"session_id": st.session_state.session_id, "trigger_reason": "USER_REQUEST"},
            )
            
            # 2. 분석 결과를 세션 상태에 저장 (다음 페이지에서 사용)
            st.session_state.analysis_result = analysis_data.get("analysis_result")
            
            st.success("✅ 대화 분석이 완료되었습니다. 상담원 화면으로 이동해주세요.")
            st.toast("분석 완료!", icon='🎉')
            
            # 3. 현재 챗봇의 대화 내용은 초기화
            # st.session_state.chatbot_messages = [] # 필요 시 주석 해제
            
            # 4. (옵션) 다음 페이지로 자동 이동
            # time.sleep(1)
            # st.switch_page("pages/01_consultation_session.py") # 파일 경로 확인 필요

        except requests.exceptions.RequestException as e:
            st.error(f"🚨 분석 API 요청 오류: {e}")
        except Exception as e:
            st.error(f"🚨 분석 중 오류 발생: {e}")

if "analysis_result" in st.session_state:
    st.info("상담원 연결이 요청되었습니다. 아래 버튼을 눌러 상담원 화면으로 이동하세요.")
    if st.button("상담원 화면으로 이동"):
        st.switch_page("pages/01_consultation_session.py")
