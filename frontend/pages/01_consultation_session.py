import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- 환경 변수 로드 ---
# 노트: 이 페이지는 여전히 고객 응답 예측을 위해 OpenAI API를 직접 사용합니다.
# 백엔드에 해당 기능이 추가되면 이 부분을 수정할 수 있습니다.
load_dotenv()

# --- 페이지 설정 ---
st.set_page_config(
    page_title="금융 AICC AI 에이전트 - 실시간 상담",
    layout="wide"
)

# --- OpenAI 클라이언트 초기화 (고객 응답 예측용) ---
try:
    if "OPENAI_API_KEY" not in os.environ:
        st.error("🚨 **OpenAI API Key 오류:** .env 파일에 `OPENAI_API_KEY`를 설정해주세요.")
        st.stop()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"🚨 OpenAI 연결 오류: {e}")
    st.stop()

# --- 시스템 역할 정의 (상담원 지원용) ---
SYSTEM_PROMPT_AGENT = """
당신은 금융권 전문 상담 AI 에이전트입니다. 상담원과의 협업을 위해, 상담원의 메모/발언에 대해 고객의 다음 대사(AI STT를 통해 들어올 예상 대사)를 짧고 자연스럽게 생성해주세요. 응답은 반드시 '고객: [STT]' 형태로 시작해야 합니다.
"""

# --- 데이터 로드 및 UI 렌더링 ---

# 이전 페이지(챗봇)에서 전달받은 분석 결과 로드
analysis_data = st.session_state.get("analysis_result")

if not analysis_data:
    st.error("🚨 사전 상담 분석 데이터가 없습니다. 고객용 챗봇 화면으로 돌아가 상담원 연결을 먼저 진행해주세요.")
    if st.button("고객용 챗봇으로 돌아가기"):
        # st.switch_page("pages/00_chatbot_temp.py") # 파일 경로 확인 필요
        st.warning("페이지 이동 기능은 앱 구조에 맞게 설정해야 합니다.")
    st.stop()

# 감정 분석 결과에 따른 이모지 반환
def get_sentiment_emoji(sentiment):
    return {"POSITIVE": "😊 긍정", "NEGATIVE": "😠 부정", "NEUTRAL": "😐 중립"}.get(sentiment, "❓")

# --- 1. 사이드바 (AI 지원 패널) 구성 ---
with st.sidebar:
    st.header("✨ AI 실시간 지원 패널")
    
    st.subheader("📝 사전 상담 요약")
    st.info(analysis_data.get("summary", "요약 정보가 없습니다."))

    st.subheader("🧐 고객 분석 정보")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "고객 감정", 
            get_sentiment_emoji(analysis_data.get("customer_sentiment"))
        )
    with col2:
        st.metric("핵심 키워드", str(len(analysis_data.get("extracted_keywords", []))) + "개")
    
    if analysis_data.get("extracted_keywords"):
        st.text(" ".join(f"#{k}" for k in analysis_data["extracted_keywords"]))

    st.subheader("📚 AI 추천 지식 (KMS)")
    recommendations = analysis_data.get("kms_recommendations", [])
    if recommendations:
        for rec in recommendations:
            st.link_button(
                f"{rec['title']} (관련도: {rec['relevance_score']:.0%})", 
                rec['url']
            )
    else:
        st.text("추천 자료가 없습니다.")
    
    st.markdown("---")
    st.text(f"분석 시간: {analysis_data.get('timestamp', 'N/A')}")


# --- 2. 메인 화면 (대화 세션) 구성 ---
st.title("📞 실시간 고객 상담 세션")
st.caption("AI Agent v1.0 - 전문 상담원 지원 시스템")

# 대화 기록 초기화
if "agent_messages" not in st.session_state:
    initial_summary = analysis_data.get("summary", "요약 정보 없음")
    initial_message = f"시스템: 보이스봇이 정리한 사전 상담 요약문입니다.\n\n---\n{initial_summary}"
    st.session_state["agent_messages"] = [
        {"role": "system", "content": initial_message},
        {"role": "user", "content": "네, 사전 상담한 내용대로 변동형 대출의 중도상환수수료에 대해 더 자세히 알고 싶습니다."}
    ]

# 대화 기록 표시
for message in st.session_state["agent_messages"]:
    role = "assistant" if message["role"] in ["system", "assistant"] else "user"
    with st.chat_message(role):
        st.markdown(message["content"])

# 새로운 입력 처리 및 LLM 호출 (고객 응답 예측)
if prompt := st.chat_input("상담원 메모 (또는 고객의 다음 질문을 직접 입력)..."):
    
    agent_memo = f"상담원 메모: {prompt}"
    st.session_state["agent_messages"].append({"role": "assistant", "content": agent_memo})
    
    with st.chat_message("assistant"):
        st.markdown(agent_memo)

    with st.chat_message("user"):
        with st.spinner("AI 에이전트가 고객의 다음 응답을 예측하는 중..."):
            
            # 예측을 위한 메시지 목록 구성
            api_messages = [{"role": "system", "content": SYSTEM_PROMPT_AGENT}]
            for msg in st.session_state["agent_messages"]:
                if msg["role"] != "system": # 시스템 메시지는 예측에 불필요
                    api_messages.append({"role": msg["role"], "content": msg["content"]})
            
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=api_messages
                )
                llm_response = response.choices[0].message.content
                
                st.markdown(llm_response)
                st.session_state["agent_messages"].append({"role": "user", "content": llm_response})
            except Exception as e:
                st.error(f"🚨 고객 응답 예측 중 오류 발생: {e}")


# --- 3. 하단 (자동화 기능 버튼) 구성 ---
st.markdown("---")
st.subheader("⚙️ 상담 후속 자동화")
if st.button("✅ **백오피스 자동 처리 완료** (CRM/DB 업데이트)", use_container_width=True):
    st.success("시스템: 상담 기록 및 처리 내용이 AI 요약 기반으로 CRM/DB에 성공적으로 반영되었습니다.")
    st.toast("저장 완료!", icon="💾")