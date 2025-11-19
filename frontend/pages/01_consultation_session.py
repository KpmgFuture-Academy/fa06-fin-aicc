import os
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st

load_dotenv()

st.set_page_config(
    page_title="금융 AICC AI 에이전트 - 실시간 상담",
    layout="wide"
)


LLM_MODE = os.getenv("AGENT_LLM_MODE", "mock").lower()
client = None

if LLM_MODE != "mock":
    try:
        api_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        st.error("🚨 OpenAI API Key가 설정되어 있지 않습니다. .env 파일을 확인해 주세요.")
        st.stop()

    try:
        client = OpenAI(api_key=api_key)
    except Exception as exc:
        st.error(f"🚨 OpenAI 초기화 오류: {exc}")
        st.stop()
else:
    st.info("현재 상담원 시뮬레이션은 Mock 모드로 동작합니다. 실제 모델을 사용하려면 `AGENT_LLM_MODE`를 변경해 주세요.")


SYSTEM_PROMPT_AGENT = """
당신은 금융 전문 상담 AI 에이전트입니다. 상담사의 메모를 참고해 고객이 말할 법한 문장을 짧고 자연스럽게 생성하세요.
답변 앞에는 반드시 '고객: '을 붙이고, 고객의 요청을 명확하게 보여 주세요.
"""


analysis_data = st.session_state.get("analysis_result")

if not analysis_data:
    st.error("🚨 사전 상담 분석 데이터가 없습니다. 고객 챗봇 화면에서 상담원 연결을 먼저 진행해 주세요.")
    if st.button("고객용 챗봇으로 돌아가기"):
        st.warning("페이지 이동 기능은 프로젝트 구조에 맞게 추가 구현해야 합니다.")
    st.stop()


def get_sentiment_label(sentiment: str) -> str:
    mapping = {
        "POSITIVE": "🙂 긍정",
        "NEGATIVE": "☹️ 부정",
        "NEUTRAL": "😐 중립",
    }
    return mapping.get(sentiment or "", "❓ 미확인")


with st.sidebar:
    st.header("AI 상담 보조 패널")
    st.subheader("사전 상담 요약")
    st.info(analysis_data.get("summary", "요약 정보가 없습니다."))

    st.subheader("고객 분석 정보")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("고객 감정", get_sentiment_label(analysis_data.get("customer_sentiment")))
    with col2:
        keywords = analysis_data.get("extracted_keywords", []) or []
        st.metric("핵심 키워드 수", str(len(keywords)))

    if keywords:
        st.text(" ".join(f"#{kw}" for kw in keywords))

    st.subheader("AI 추천 자료 (KMS)")
    recommendations = analysis_data.get("kms_recommendations", []) or []
    if recommendations:
        for rec in recommendations:
            st.link_button(
                f"{rec['title']} (관계도 {rec['relevance_score']:.0%})",
                rec["url"]
            )
    else:
        st.text("추천 자료가 없습니다.")

    st.markdown("---")
    st.text(f"분석 시각: {analysis_data.get('timestamp', 'N/A')}")


st.title("🧑 실시간 상담 세션")
st.caption("AI Agent v1.0 - 상담 예측 보조 시뮬레이션")


if "agent_messages" not in st.session_state:
    initial_summary = analysis_data.get("summary", "요약 정보 없음")
    intro_message = f"시스템: 아래는 고객 챗봇 분석 요약입니다.\n\n---\n{initial_summary}"
    st.session_state["agent_messages"] = [
        {"role": "system", "content": intro_message},
        {"role": "user", "content": "고객: 챗봇 상담 내용을 상담원에게 다시 확인받고 싶습니다."},
    ]


def render_chat_history():
    for entry in st.session_state["agent_messages"]:
        role = "assistant" if entry["role"] in {"system", "assistant"} else "user"
        with st.chat_message(role):
            st.markdown(entry["content"])


def predict_customer_reply(api_messages):
    if LLM_MODE == "mock":
        last_note = next(
            (msg["content"] for msg in reversed(st.session_state["agent_messages"]) if msg["role"] == "assistant"),
            ""
        )
        memo_text = last_note.replace("상담 메모:", "").strip() or "상담 메모를 바탕으로 도와주세요."
        return f"고객: 방금 남겨주신 '{memo_text}' 내용에 대해 조금 더 설명해 주실 수 있나요?"

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=api_messages,
    )
    return response.choices[0].message.content


render_chat_history()


if prompt := st.chat_input("상담 메모 또는 고객 예상 질문을 입력해 주세요."):
    memo_text = f"상담 메모: {prompt}"
    st.session_state["agent_messages"].append({"role": "assistant", "content": memo_text})

    with st.chat_message("assistant"):
        st.markdown(memo_text)

    with st.chat_message("user"):
        with st.spinner("AI 에이전트가 고객 응답을 예측하고 있습니다..."):
            api_messages = [{"role": "system", "content": SYSTEM_PROMPT_AGENT}]
            for msg in st.session_state["agent_messages"]:
                if msg["role"] != "system":
                    api_messages.append({"role": msg["role"], "content": msg["content"]})

            try:
                reply = predict_customer_reply(api_messages)
                st.markdown(reply)
                st.session_state["agent_messages"].append({"role": "user", "content": reply})
            except Exception as exc:
                st.error(f"🚨 고객 응답 예측 중 오류가 발생했습니다: {exc}")


st.markdown("---")
st.subheader("상담 후속 자동화")
if st.button("✅ 백오피스 자동 처리 완료 (CRM/DB 업데이트)", use_container_width=True):
    st.success("백오피스 시스템에 상담 요약과 메모가 반영되었습니다.")
    st.toast("처리 완료!", icon="✅")
