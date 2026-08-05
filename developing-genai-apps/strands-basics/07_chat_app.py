"""Streamlit 채팅 앱 — 웹 브라우저에서 에이전트와 대화합니다."""
import streamlit as st
from strands import Agent
from strands.models import BedrockModel
from tools import search_restaurants, create_reservation

REGION = "us-west-2"

st.set_page_config(page_title="🍽️ 식당 컨시어지", page_icon="🍽️")
st.title("🍽️ 강남 식당 컨시어지")
st.caption("식당 검색과 예약을 도와드립니다. 무엇이든 물어보세요!")

@st.cache_resource
def get_agent():
    """에이전트를 생성하고 캐싱합니다."""
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-6",
        region_name=REGION,
    )
    return Agent(
        model=model,
        system_prompt="""당신은 강남 지역 전문 식당 컨시어지 AI입니다.

역할:
- search_restaurants 도구로 조건에 맞는 식당을 검색합니다
- create_reservation 도구로 예약을 진행합니다
- 고객의 요구사항을 친절하게 파악합니다

규칙:
- 한국어로 답변합니다
- 반드시 도구를 사용하여 실제 데이터를 기반으로 추천합니다
- 정보가 부족하면 먼저 질문합니다
- 마크다운 형식으로 보기 좋게 답변합니다""",
        tools=[search_restaurants, create_reservation],
        callback_handler=None,  # 서버 콘솔로의 스트리밍 출력 끄기 — UI에는 str(response)만 표시
    )

# 채팅 히스토리 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 이전 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("식당 추천이나 예약을 요청해보세요..."):
    # 사용자 메시지 표시 및 저장
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 에이전트 응답 생성
    with st.chat_message("assistant"):
        with st.spinner("검색 중..."):
            agent = get_agent()
            response = agent(prompt)
            response_text = str(response)
            st.markdown(response_text)

    # 어시스턴트 메시지 저장
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )