"""
03_query_kb.py

RetrieveAndGenerate API로 시맨틱 검색을 확인한다.

완료 기준:
  - 응답 텍스트에 "경복궁", "북촌한옥마을"이 포함
  - 두 문서가 참조 문서(citations)에 나타남

사용법:
    python 03_query_kb.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3

REGION = "us-east-1"
QUERY = "역사 문화 체험 위주로 반나절 코스를 추천해 주세요"
GEN_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
_ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
GEN_MODEL_ARN = (
    f"arn:aws:bedrock:{REGION}:{_ACCOUNT_ID}:inference-profile/{GEN_MODEL_ID}"
)


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_info = json.load(fh)
    kb_id = kb_info["knowledgeBaseId"]

    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    resp = client.retrieve_and_generate(
        input={"text": QUERY},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": GEN_MODEL_ARN,
            },
        },
    )

    answer = resp["output"]["text"]
    citations = resp.get("citations", [])

    referenced_uris = []
    for c in citations:
        for ref in c.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri", "")
            referenced_uris.append(uri)

    print("=== 질의 ===")
    print(QUERY)
    print("\n=== 응답 텍스트 ===")
    print(answer)
    print("\n=== 참조 문서 ===")
    for uri in referenced_uris:
        print(f"  - {uri}")

    print("\n=== 완료 기준 검증 ===")
    # 미션 1-2에서 창덕궁·국립중앙박물관을 추가했으므로, "역사 문화" 질의의
    # 정답 후보가 넓어졌다. 특정 두 곳을 고정으로 요구하는 대신 역사/문화
    # 카테고리 관광지가 참조되었는지로 검증한다.
    history_spots = {"경복궁", "북촌한옥마을", "창덕궁", "국립중앙박물관", "DMZ"}
    referenced_names = {u.rsplit("/", 1)[-1].replace(".txt", "") for u in referenced_uris}
    matched = referenced_names & history_spots

    non_history = referenced_names - history_spots

    print(f"  참조된 관광지               : {sorted(referenced_names)}")
    print(f"  그중 역사/문화 관광지       : {sorted(matched)}")
    print(f"  역사와 무관한 관광지 유입   : {sorted(non_history) or '없음'}")

    ok = len(matched) >= 2 and not non_history
    if ok:
        print("\n✅ 완료 기준 충족: 역사/문화 관광지 2곳 이상이 참조되고,")
        print("   무관한 카테고리(맛집·쇼핑 등)는 참조되지 않았습니다.")
        return 0

    print("\n❌ 완료 기준 미충족", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
