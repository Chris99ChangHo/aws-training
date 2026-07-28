"""
app.py

서울 여행 Knowledge Base(travel-planner-kb) 기반 대화형 추천 챗봇.

Streamlit 채팅 인터페이스에서 질문을 입력하면 Bedrock의
RetrieveAndGenerate API로 KB를 검색해 답변과 참조 문서를 표시한다.

실행:
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import streamlit as st

REGION = "us-east-1"
KB_INFO_PATH = Path(__file__).parent / "kb_info.json"

# 생성 모델. inference profile ARN이 필요해 계정 ID를 런타임에 조회한다.
GEN_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# 사이드바 카테고리 드롭다운.
# 값은 실제 메타데이터(travel-kb-ko/metadata/*.metadata.json)의 category와
# 매핑된다. "역사/문화"는 역사 관련 관광지(경복궁·북촌한옥마을·DMZ 등)를
# 모두 포함하도록 stringContains("역사")로 필터링한다.
CATEGORY_OPTIONS: dict[str, dict | None] = {
    "전체": None,
    "역사/문화": {"stringContains": {"key": "category", "value": "역사"}},
    "랜드마크": {"equals": {"key": "category", "value": "랜드마크"}},
    "쇼핑/카페": {"equals": {"key": "category", "value": "쇼핑/카페"}},
    "맛집/시장": {"equals": {"key": "category", "value": "맛집/시장"}},
    "자연/공원": {"equals": {"key": "category", "value": "자연/공원"}},
}

# 테마별 색상 토큰. 라이트/다크 전환 시 이 값들로 CSS를 다시 그린다.
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#FFFFFF",
        "bg_secondary": "#F7F8FA",
        "text": "#1A1A2E",
        "text_muted": "#6B7280",
        "accent": "#1D4ED8",
        "accent_soft": "#DBEAFE",
        "card_bg": "#FFFFFF",
        "card_border": "#E5E7EB",
        "user_bubble": "#2563EB",
        "user_text": "#FFFFFF",
        "assistant_bubble": "#F1F3F6",
        "assistant_text": "#1A1A2E",
    },
    "dark": {
        "bg": "#0F1117",
        "bg_secondary": "#171A21",
        "text": "#E5E7EB",
        "text_muted": "#9CA3AF",
        "accent": "#60A5FA",
        "accent_soft": "#1E3A5F",
        "card_bg": "#1B1F27",
        "card_border": "#2A2F3A",
        "user_bubble": "#2563EB",
        "user_text": "#FFFFFF",
        "assistant_bubble": "#1B1F27",
        "assistant_text": "#E5E7EB",
    },
}


def inject_theme_css(mode: str) -> None:
    """선택된 테마 색상으로 커스텀 CSS를 주입해 UI를 다듣는다."""
    t = THEMES[mode]
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {t['bg']};
            color: {t['text']};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {t['bg_secondary']};
            border-right: 1px solid {t['card_border']};
        }}
        h1, h2, h3, h4, p, span, label {{
            color: {t['text']} !important;
        }}
        .app-header {{
            padding: 0.5rem 0 1.2rem 0;
            border-bottom: 1px solid {t['card_border']};
            margin-bottom: 1.2rem;
        }}
        .app-header .subtitle {{
            color: {t['text_muted']} !important;
            font-size: 0.92rem;
        }}
        div[data-testid="stChatMessage"] {{
            background-color: {t['assistant_bubble']};
            border-radius: 14px;
            padding: 0.4rem 0.2rem;
            margin-bottom: 0.4rem;
        }}
        .destination-card {{
            background-color: {t['card_bg']};
            border: 1px solid {t['card_border']};
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 8px;
        }}
        .destination-card h4 {{
            margin: 0 0 6px 0;
            font-size: 1.02rem;
        }}
        .destination-card .meta-row {{
            font-size: 0.86rem;
            color: {t['text_muted']} !important;
            margin: 2px 0;
        }}
        .destination-card .badge {{
            display: inline-block;
            background-color: {t['accent_soft']};
            color: {t['accent']} !important;
            font-size: 0.76rem;
            font-weight: 600;
            padding: 2px 9px;
            border-radius: 999px;
            margin-bottom: 6px;
        }}
        .destination-card .uri {{
            font-size: 0.72rem;
            color: {t['text_muted']} !important;
            word-break: break-all;
            margin-top: 6px;
        }}
        div[data-testid="stChatInput"] textarea {{
            background-color: {t['bg_secondary']};
            color: {t['text']};
        }}
        .stButton>button {{
            border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_gen_model_arn() -> str:
    account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    return f"arn:aws:bedrock:{REGION}:{account_id}:inference-profile/{GEN_MODEL_ID}"


@st.cache_resource
def get_kb_id() -> str:
    with open(KB_INFO_PATH, encoding="utf-8") as fh:
        return json.load(fh)["knowledgeBaseId"]


@st.cache_resource
def get_client():
    return boto3.client("bedrock-agent-runtime", region_name=REGION)


@st.cache_resource
def get_destination_info() -> dict[str, dict]:
    """참조 문서 카드에 표시할 관광지별 카테고리/소요시간 정보를 로드한다."""
    meta_dir = Path(__file__).parent / "travel-kb-ko" / "metadata"
    info: dict[str, dict] = {}
    if not meta_dir.exists():
        return info
    for meta_path in meta_dir.glob("*.metadata.json"):
        name = meta_path.name.replace(".metadata.json", "")
        with open(meta_path, encoding="utf-8") as fh:
            attrs = json.load(fh).get("metadataAttributes", {})
        info[name] = attrs
    return info


def render_source_cards(sources: list[str], destination_info: dict[str, dict]) -> None:
    """참조 문서를 관광지 카드 형태로 렌더링한다."""
    if not sources:
        return

    st.markdown("**📍 추천 관광지**")
    cols = st.columns(min(len(sources), 3))
    for idx, uri in enumerate(sources):
        name = uri.rsplit("/", 1)[-1].replace(".txt", "")
        attrs = destination_info.get(name, {})
        category = attrs.get("category", "")
        location = attrs.get("location", "")
        duration = attrs.get("duration_hours", "")

        with cols[idx % len(cols)]:
            meta_lines = ""
            if location:
                meta_lines += f'<div class="meta-row">📌 {location}</div>'
            if duration:
                meta_lines += f'<div class="meta-row">⏱ 약 {duration}시간</div>'

            st.markdown(
                f"""
                <div class="destination-card">
                    {f'<span class="badge">{category}</span>' if category else ''}
                    <h4>{name}</h4>
                    {meta_lines}
                    <div class="uri">{uri}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def query_kb(
    client,
    kb_id: str,
    question: str,
    category_filter: dict | None = None,
    session_id: str | None = None,
) -> tuple[str, list[str], str]:
    """RetrieveAndGenerate를 호출해 (답변 텍스트, 참조 문서 URI 목록, sessionId)를 반환한다.

    category_filter가 주어지면 vectorSearchConfiguration.filter로 전달되어
    해당 카테고리의 관광지 문서만 검색 대상에 포함된다.

    session_id가 주어지면 Bedrock이 이전 대화 컨텍스트를 유지한 채 응답을
    생성한다("그중에서 무료인 곳은?" 같은 후속 질문 처리에 필요).
    """
    kb_config: dict = {
        "knowledgeBaseId": kb_id,
        "modelArn": get_gen_model_arn(),
    }
    if category_filter is not None:
        kb_config["retrievalConfiguration"] = {
            "vectorSearchConfiguration": {"filter": category_filter}
        }

    request: dict = {
        "input": {"text": question},
        "retrieveAndGenerateConfiguration": {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": kb_config,
        },
    }
    if session_id:
        request["sessionId"] = session_id

    resp = client.retrieve_and_generate(**request)
    answer = resp["output"]["text"]
    new_session_id = resp["sessionId"]

    uris: list[str] = []
    for citation in resp.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            if uri and uri not in uris:
                uris.append(uri)

    return answer, uris, new_session_id


def main() -> None:
    st.set_page_config(
        page_title="서울 여행 추천 챗봇",
        page_icon="🗺️",
        layout="centered",
    )

    if "theme" not in st.session_state:
        st.session_state.theme = "light"

    inject_theme_css(st.session_state.theme)

    try:
        kb_id = get_kb_id()
    except FileNotFoundError:
        st.error(
            "kb_info.json을 찾을 수 없습니다. 먼저 setup_02_create_kb.py를 "
            "실행해 Knowledge Base를 생성해 주세요."
        )
        return

    client = get_client()
    destination_info = get_destination_info()

    with st.sidebar:
        st.header("⚙️ 설정")

        is_dark = st.session_state.theme == "dark"
        toggled = st.toggle("🌙 다크 모드", value=is_dark)
        new_theme = "dark" if toggled else "light"
        if new_theme != st.session_state.theme:
            st.session_state.theme = new_theme
            st.rerun()

        st.divider()
        st.subheader("검색 필터")
        selected_category = st.selectbox(
            "카테고리", options=list(CATEGORY_OPTIONS.keys()), index=0
        )
        st.caption("선택한 카테고리의 관광지만 검색 대상에 포함됩니다.")

        st.divider()
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.session_state.bedrock_session_id = None
            st.rerun()

    category_filter = CATEGORY_OPTIONS[selected_category]

    st.markdown(
        """
        <div class="app-header">
            <h1 style="margin-bottom:0.2rem;">🗺️ 서울 여행 추천 챗봇</h1>
            <div class="subtitle">Amazon Bedrock Knowledge Base 기반 대화형 추천</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "bedrock_session_id" not in st.session_state:
        # None이면 다음 요청에서 새 대화 세션을 시작한다.
        st.session_state.bedrock_session_id = None

    # 기존 대화 내역 표시 (멀티턴: 이전 질문/답변이 화면에 계속 남는다)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                render_source_cards(msg["sources"], destination_info)

    # 새 질문 입력
    question = st.chat_input(
        "서울 여행에 대해 물어보세요 (예: 경복궁 입장료가 얼마예요? / 그중에서 무료인 곳은?)"
    )
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Knowledge Base 검색 중..."):
            try:
                answer, sources, session_id = query_kb(
                    client,
                    kb_id,
                    question,
                    category_filter,
                    st.session_state.bedrock_session_id,
                )
            except Exception as exc:  # noqa: BLE001 - 사용자에게 에러 표시
                st.error(f"검색 중 오류가 발생했습니다: {exc}")
                return

        # 다음 질문부터 이 sessionId로 이어서 호출하면 이전 대화 맥락이
        # 유지된다 ("그중에서 무료인 곳은?" 같은 후속 질문 처리).
        st.session_state.bedrock_session_id = session_id

        st.markdown(answer)
        render_source_cards(sources, destination_info)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


if __name__ == "__main__":
    main()
