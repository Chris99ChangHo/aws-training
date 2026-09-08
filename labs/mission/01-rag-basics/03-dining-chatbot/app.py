# app.py — 메타데이터 필터를 활용한 대화형 식당 추천 챗봇
#
# 사이드바에서 카테고리 / 지역 / 예산을 필터로 설정하면, retrieve_and_generate
# 호출 시 Knowledge Base 검색을 해당 조건으로 좁혀서 답변을 생성합니다.
# st.session_state로 대화 히스토리를 유지해 멀티턴 대화가 가능합니다.
# 사전 단계: 01-build-kb(KB 생성) → 02-advanced-kb-search(필터/검색 실습)에서
# 확인한 KNOWLEDGE_BASE_ID와 메타데이터 필드(category/location/price_min 등)를 그대로 사용합니다.
import os

import boto3
import streamlit as st

REGION = "us-west-2"
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")
INFERENCE_PROFILE_ID = "us.anthropic.claude-sonnet-4-6"

st.set_page_config(page_title="강남 다이닝 추천 챗봇", page_icon="🍽️")
st.title("🍽️ 강남 다이닝 추천 챗봇")
st.caption("메타데이터 필터(카테고리 · 지역 · 예산)로 Knowledge Base 검색을 좁혀 답변합니다.")

if KNOWLEDGE_BASE_ID == "<YOUR_KNOWLEDGE_BASE_ID>":
    st.warning(
        "KNOWLEDGE_BASE_ID가 설정되지 않았습니다. "
        "환경변수 `KNOWLEDGE_BASE_ID`로 주입하거나 코드 상단을 직접 수정하세요."
    )
    st.stop()

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

# --- 사이드바: 사용 리소스 정보 + 메타데이터 필터 ---
with st.sidebar:
    st.caption(
        "🧠 **Amazon Bedrock Knowledge Bases**  ·  "
        "🗂️ **Amazon S3**  ·  🤖 **Claude\u00a0Sonnet\u00a04.6**"
    )
    with st.expander("🔧 사용 리소스 정보"):
        st.code(
            f"Region: {REGION}\nKnowledge Base ID: {KNOWLEDGE_BASE_ID}\nModel: {INFERENCE_PROFILE_ID}",
            language="text",
        )

    st.header("🔎 필터")

    category = st.selectbox(
        "카테고리",
        ["전체", "한식", "일식", "중식", "이탈리안", "프렌치", "채식/비건"],
    )
    location = st.selectbox(
        "지역",
        ["전체", "강남역", "역삼역", "압구정역", "선릉역", "삼성역"],
    )
    budget = st.slider(
        "1인 예산 (원)",
        min_value=0,
        max_value=100000,
        value=100000,
        step=5000,
        help="선택한 금액 이하로 최소 가격(price_min)이 형성된 식당만 검색합니다.",
    )
    top_k = st.slider("검색 결과 수", min_value=1, max_value=10, value=5)

    if st.button("🗑️ 대화 초기화"):
        st.session_state.messages = []
        st.rerun()


def build_filter(category, location, budget):
    """선택된 필터들을 KB의 AND 조건으로 조합. 전체 선택 시 조건 생략."""
    conditions = []
    if category != "전체":
        conditions.append({"equals": {"key": "category", "value": category}})
    if location != "전체":
        conditions.append({"equals": {"key": "location", "value": location}})
    if budget < 100000:
        # price_min이 예산 이하인 식당만 (즉, 감당 가능한 최소 가격대)
        conditions.append({"lessThanOrEquals": {"key": "price_min", "value": budget}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"andAll": conditions}


# --- 대화 히스토리 초기화 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 기존 대화 렌더링 ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("참조 문서"):
                for uri in msg["citations"]:
                    st.caption(uri)

# --- 사용자 입력 ---
question = st.chat_input("예: 데이트하기 좋은 곳 추천해 주세요")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    kb_filter = build_filter(category, location, budget)

    retrieval_cfg = {"numberOfResults": top_k}
    if kb_filter:
        retrieval_cfg["filter"] = kb_filter

    with st.chat_message("assistant"):
        with st.spinner("검색 중..."):
            response = agent_rt.retrieve_and_generate(
                input={"text": question},
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                        "modelArn": INFERENCE_PROFILE_ID,
                        "retrievalConfiguration": {
                            "vectorSearchConfiguration": retrieval_cfg
                        },
                    },
                },
            )

        answer = response["output"]["text"]
        st.markdown(answer)

        citation_uris = []
        for citation in response.get("citations", []):
            for ref in citation.get("retrievedReferences", []):
                uri = ref["location"]["s3Location"]["uri"]
                citation_uris.append(uri)

        if citation_uris:
            with st.expander("참조 문서"):
                for uri in citation_uris:
                    st.caption(uri)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "citations": citation_uris}
    )
