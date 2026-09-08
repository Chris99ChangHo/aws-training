"""팀 코딩 콘솔 — AgentCore Runtime의 CodingService를 호출하고,
S3 Files에 영속 저장된 작업 이력을 표로 조회한다.

실행 전 RUNTIME_ARN과 BUCKET을 채워야 한다.
"""
import json
import uuid

import boto3
import streamlit as st

REGION = "us-west-2"
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-west-2:000000000000:runtime/CodingService_CodingService-wexBNxC63R"
BUCKET = "coding-service-files-000000000000"

agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)

st.set_page_config(page_title="팀 코딩 콘솔", page_icon="🛠️")
st.title("🛠️ 팀 코딩 콘솔")


def load_work_log() -> list[dict]:
    """S3에서 작업 이력을 읽어 시간 역순으로 반환한다."""
    try:
        obj = s3_client.get_object(Bucket=BUCKET, Key="work-log.json")
        logs = json.loads(obj["Body"].read())
    except s3_client.exceptions.NoSuchKey:
        return []
    return sorted(logs, key=lambda e: e["timestamp"], reverse=True)


request_text = st.text_area(
    "코딩 요청",
    placeholder="예: reservation.py에 영업시간 검증을 추가해 주세요",
)
target_path = st.text_input(
    "리뷰 루프 대상 파일 (선택)",
    placeholder="비워두면 단순 요청, 채우면 Coder→Reviewer→Tester 루프",
)

if st.button("실행", type="primary") and request_text.strip():
    with st.spinner("에이전트가 작업 중입니다..."):
        payload: dict = {"prompt": request_text}
        if target_path.strip():
            payload["target_path"] = target_path.strip()
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=f"console-{uuid.uuid4().hex}",
            payload=json.dumps(payload).encode(),
        )
        body = json.loads(response["response"].read())
    st.success("완료")
    st.markdown(body["result"])

st.divider()
st.subheader("작업 이력")

logs = load_work_log()
if logs:
    st.dataframe(
        [
            {
                "시간": entry["timestamp"],
                "요청": entry["request"][:60],
                "결과 요약": entry["result"][:80],
            }
            for entry in logs
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("아직 작업 이력이 없습니다. 위에서 요청을 실행해 보세요.")
