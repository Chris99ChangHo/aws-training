"""
02_hybrid_search.py

시맨틱 vs 하이브리드 서치 비교.

세부 절차·원리는 seoul-travel-planner-kb/02_hybrid_search.py 참고.
이 스크립트는 이 미션의 고유 질문만 담는다.

질문: "트라토리아 벨라 메뉴 가격" — 문서 본문에만 있는 고유 키워드
(상호명 "트라토리아 벨라")가 포함된 질의라 하이브리드 효과를
관찰하기 좋다.

사용법:
    python 02_hybrid_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

REGION = "us-west-2"
QUERY = "트라토리아 벨라 메뉴 가격"


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def retrieve(client, kb_id: str, search_type: str) -> list[tuple[str, float]]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": 5,
                "overrideSearchType": search_type,
            }
        },
    )
    return [
        (name_of(r["location"]["s3Location"]["uri"]), round(r.get("score", 0.0), 4))
        for r in resp["retrievalResults"]
    ]


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}\n")

    sem = retrieve(client, kb_id, "SEMANTIC")
    hyb = retrieve(client, kb_id, "HYBRID")

    print("=== SEMANTIC ===")
    for i, (n, s) in enumerate(sem, 1):
        print(f"  {i}. {n:20s} {s}")

    print("\n=== HYBRID ===")
    for i, (n, s) in enumerate(hyb, 1):
        print(f"  {i}. {n:20s} {s}")

    same = sem == hyb
    print(f"\n{'=' * 60}")
    print(f"두 방식 결과 동일 여부: {same}")
    if same:
        print("=> '트라토리아 벨라'라는 고유 상호명이 이미 시맨틱만으로도")
        print("   압도적으로 잘 잡혀서, 이 질의에서는 하이브리드의 키워드")
        print("   매칭 보너스가 순위에 추가로 드러나지 않았다.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
