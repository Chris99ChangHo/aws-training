# app.py — 파이프라인이 배포한 AgentCore Runtime을 호출하는 미니 Streamlit 앱
#
# 소스를 수정해 source.zip을 재업로드하면 dining-pipeline이 자동으로
# Test → Deploy를 거쳐 새 버전을 배포합니다. 이 앱은 코드 변경 없이
# Runtime의 기본 엔드포인트를 그대로 호출하므로, 파이프라인이 새 버전을
# 배포하면 이 앱의 응답도 자동으로 바뀝니다.
import streamlit as st

from test_invoke import invoke_agent

st.title("🍽️ 강남 다이닝 컨시어지 (CI/CD 배포)")
st.caption("dining-pipeline이 배포한 DiningConcierge Runtime을 호출합니다.")

question = st.chat_input("질문을 입력하세요")
if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Runtime 호출 중..."):
            try:
                answer = invoke_agent(question)
            except Exception as e:
                answer = f"⚠️ Runtime 호출 실패: {e}"
        st.markdown(answer)
