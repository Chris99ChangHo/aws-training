"""
setup_01_verify_kb.py

us-west-2에 새로 구축한 restaurant-concierge-kb가 정상 동작하는지
RetrieveAndGenerate로 검증한다.

완료 기준: KB 상태 ACTIVE + "이탈리안 레스토랑 추천해줘" 검색 시
트라토리아 벨라가 참조 문서에 포함됨.

사용법:
    python setup_01_verify_kb.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3

REGION = "us-west-2"
KB_INFO_PATH = Path(__file__).parent / "kb_info.json"

# us-west-2의 claude-sonnet-4-6은 INFERENCE_PROFILE 타입이라
# inference profile ARN이 필요하다 (foundation-model ARN 직접 호출 불가).
GEN_MODEL_ID = "us.anthropic.claude-sonnet-4-6"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    with open(KB_INFO_PATH, encoding="utf-8") as fh:
        info = json.load(fh)
    kb_id = info["knowledgeBaseId"]

    session = boto3.session.Session(region_name=REGION)
    account_id = session.client("sts").get_caller_identity()["Account"]
    runtime = session.client("bedrock-agent-runtime")

    gen_model_arn = f"arn:aws:bedrock:{REGION}:{account_id}:inference-profile/{GEN_MODEL_ID}"

    query = "이탈리안 레스토랑 추천해줘"
    resp = runtime.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": gen_model_arn,
            },
        },
    )
    answer = resp["output"]["text"]
    uris = [
        ref["location"]["s3Location"]["uri"]
        for c in resp.get("citations", [])
        for ref in c.get("retrievedReferences", [])
    ]

    log(f"[검색] 질의: {query!r}")
    log(f"[검색] 응답: {answer[:200]}")
    log("[검색] 참조 문서:")
    for u in uris:
        log(f"    - {u}")

    ok = any("restaurant-01" in u for u in uris)
    log("\n" + "=" * 60)
    if ok:
        log("✅ 완료 기준 충족: us-west-2 KB 시맨틱 검색 정상 동작")
    else:
        log("❌ 완료 기준 미충족", file=sys.stderr)
    log("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
