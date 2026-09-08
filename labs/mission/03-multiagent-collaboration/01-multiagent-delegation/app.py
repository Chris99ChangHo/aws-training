# app.py — 오케스트레이터의 Streamlit 미니 챗
import streamlit as st

import orchestrator
from orchestrator import orchestrator as dining_orchestrator

st.set_page_config(page_title="강남 다이닝 오케스트레이터", page_icon="🍽️")
st.title("🍽️ 강남 다이닝 오케스트레이터")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("delegated_to"):
            st.caption("위임: " + " → ".join(msg["delegated_to"]))

question = st.chat_input("무엇을 도와드릴까요?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    orchestrator.delegation_log.clear()

    with st.chat_message("assistant"):
        with st.spinner("전문가에게 확인 중..."):
            response = dining_orchestrator(question)
        answer = str(response)
        st.markdown(answer)

        delegated_to = list(orchestrator.delegation_log)
        if delegated_to:
            st.caption("위임: " + " → ".join(delegated_to))

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "delegated_to": delegated_to}
    )
