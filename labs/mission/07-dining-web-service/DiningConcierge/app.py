# app.py — 배포된 AgentCore Runtime을 호출하는 미니 Streamlit 앱
import streamlit as st

from test_invoke import invoke_agent

st.title("🍽️ 강남 다이닝 컨시어지 (AgentCore Runtime)")

question = st.chat_input("질문을 입력하세요")
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Runtime 호출 중..."):
            answer = invoke_agent(question)
        st.markdown(answer)
