# app.py — Streamlit 다이닝 컨시어지 챗봇
import uuid

import streamlit as st

from agent import create_agent
from tools import RESTAURANTS

st.set_page_config(page_title="강남 다이닝 컨시어지", page_icon="🍽️")
st.title("🍽️ 강남 다이닝 컨시어지")

if "session_id" not in st.session_state:
    st.session_state.session_id = "strands-app-session"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tool_log" not in st.session_state:
    st.session_state.tool_log = []

with st.sidebar:
    st.caption(f"🗂️ session_id: `{st.session_state.session_id}`")
    if st.button("🔄 세션 초기화 (새 대화 시작)"):
        st.session_state.session_id = f"strands-app-{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.session_state.tool_log = []
        st.rerun()

    st.header("🛠️ 도구 호출 로그")
    log_placeholder = st.container()
    for entry in st.session_state.tool_log:
        log_placeholder.caption(entry)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("mentioned_restaurants"):
            cols = st.columns(len(msg["mentioned_restaurants"]))
            for col, r in zip(cols, msg["mentioned_restaurants"]):
                with col:
                    st.markdown(f"**{r['name']}**")
                    st.caption(f"{r['cuisine']} · {r['price_range']}")

question = st.chat_input("무엇을 도와드릴까요?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    tool_events = []

    def collect_callback(**kwargs):
        tu = kwargs.get("current_tool_use")
        if tu and tu.get("name"):
            label = f"🔧 도구 호출: `{tu['name']}`"
            if not tool_events or tool_events[-1] != label:
                tool_events.append(label)

    agent, mcp_client = create_agent(
        session_id=st.session_state.session_id, callback_handler=collect_callback
    )
    try:
        with st.chat_message("assistant"):
            with st.spinner("확인 중..."):
                response = agent(question)
            answer = str(response)
            st.markdown(answer)

            # 응답에서 언급된 식당을 찾아 카드로 표시
            mentioned = [r for r in RESTAURANTS if r["name"] in answer]
            if mentioned:
                cols = st.columns(len(mentioned))
                for col, r in zip(cols, mentioned):
                    with col:
                        st.markdown(f"**{r['name']}**")
                        st.caption(f"{r['cuisine']} · {r['location']}")
                        st.caption(f"{r['price_range']} · ⭐{r['rating']}")
    finally:
        mcp_client.stop(None, None, None)

    st.session_state.tool_log.extend(tool_events)
    with st.sidebar:
        for entry in tool_events:
            st.caption(entry)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "mentioned_restaurants": mentioned,
        }
    )
