# app.py — 미니 검색창 (필터 조건 전환 비교)
import os

import boto3
import streamlit as st

REGION = "us-west-2"
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")

st.set_page_config(page_title="강남 다이닝 KB 검색", page_icon="🔍")
st.title("🔍 강남 다이닝 KB 검색")

# --- 실습에 사용된 AWS 서비스 표시 (포트폴리오/스크린샷용) ---
st.caption(
    "🧠 **Amazon Bedrock Knowledge Bases** (Retrieve API, 메타데이터 필터)  ·  "
    "🔎 **OpenSearch Serverless** (벡터 검색 백엔드)"
)
with st.expander("🔧 사용 리소스 정보", expanded=False):
    st.code(f"Region: {REGION}\nKnowledge Base ID: {KNOWLEDGE_BASE_ID}", language="text")

if KNOWLEDGE_BASE_ID == "<YOUR_KNOWLEDGE_BASE_ID>":
    st.warning(
        "KNOWLEDGE_BASE_ID가 설정되지 않았습니다. "
        "환경변수 `KNOWLEDGE_BASE_ID`로 주입하거나 코드 상단을 직접 수정하세요."
    )
    st.stop()

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

query = st.text_input("질문을 입력하세요")
category = st.selectbox("카테고리 필터", ["없음", "한식"])

if query:
    vector_cfg = {"numberOfResults": 5}
    # 💡: "없음"이면 filter 키 자체를 생략합니다 — 빈 filter는 ValidationException
    if category != "없음":
        vector_cfg["filter"] = {"equals": {"key": "category", "value": category}}
    resp = agent_rt.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": vector_cfg},
    )
    for i, r in enumerate(resp["retrievalResults"], 1):
        meta = r.get("metadata", {})
        st.markdown(f"**{i}. [{meta.get('category', '-')}]** {r['content']['text'][:200]}")