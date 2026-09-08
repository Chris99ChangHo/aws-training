# app.py — KB 검색 미니 검색창 (입력창 + 답변 표시만)
import os

import boto3
import streamlit as st

REGION = "us-west-2"
# 환경변수 KNOWLEDGE_BASE_ID로 주입하거나 아래 기본값을 직접 채워도 됩니다.
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")
INFERENCE_PROFILE_ID = "us.anthropic.claude-sonnet-4-6"

st.set_page_config(page_title="강남 다이닝 검색", page_icon="🍽️")
st.title("🍽️ 강남 다이닝 검색")

# --- 실습에 사용된 AWS 서비스 표시 (포트폴리오/스크린샷용) ---
st.caption(
    "🧠 **Amazon Bedrock Knowledge Bases** (RetrieveAndGenerate)  ·  "
    "🗂️ **Amazon S3** (원본 문서)  ·  "
    "🤖 **Claude\u00a0Sonnet\u00a04.6** (응답 생성)"
)
with st.expander("🔧 사용 리소스 정보", expanded=False):
    st.code(
        f"Region: {REGION}\n"
        f"Knowledge Base ID: {KNOWLEDGE_BASE_ID}\n"
        f"Model: {INFERENCE_PROFILE_ID}",
        language="text",
    )

if KNOWLEDGE_BASE_ID == "<YOUR_KNOWLEDGE_BASE_ID>":
    st.warning(
        "KNOWLEDGE_BASE_ID가 설정되지 않았습니다. "
        "콘솔에서 KB를 만든 뒤 이 값을 채워주세요 "
        "(환경변수 `KNOWLEDGE_BASE_ID`로 주입하거나 코드 상단을 직접 수정)."
    )
    st.stop()

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

question = st.text_input("질문을 입력하세요")
if question:
    response = agent_rt.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": INFERENCE_PROFILE_ID,
            },
        },
    )
    st.write(response["output"]["text"])

    # 💡: 근거 문서도 함께 표시 — KB 근거 답변인지 눈으로 확인
    with st.expander("📄 참조 문서 (KB 근거)"):
        for citation in response.get("citations", []):
            for ref in citation.get("retrievedReferences", []):
                st.caption(ref["location"]["s3Location"]["uri"])