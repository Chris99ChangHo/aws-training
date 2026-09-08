"""
02_hybrid_search.py

하이브리드 서치(SEMANTIC vs HYBRID) 비교.

Retrieve API의 vectorSearchConfiguration.overrideSearchType 으로 검색 방식을
지정한다.
  - SEMANTIC : 벡터 임베딩 유사도만 사용
  - HYBRID   : 벡터 유사도 + 원문 키워드 매칭을 결합 (재현율 향상)

주의: 하이브리드는 OpenSearch Serverless 벡터 스토어에 filterable text
필드가 있어야 동작한다. 또한 질의가 이미 시맨틱만으로 압도적으로 잘
잡히는 경우(예: "경복궁 입장료")에는 두 방식의 결과가 사실상 같아서
차이를 관찰할 수 없다. 차이는 다음 상황에서 드러난다:
  - 문서 안에만 등장하는 고유명사/숫자를 질의로 쓸 때
  - 시맨틱 점수가 서로 촘촘하게 붙어 순위가 뒤섞일 때

사용법:
    python 02_hybrid_search.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3

REGION = "us-east-1"

# (질의, 기대하는 정답 문서) - 문서 본문에만 등장하는 고유 키워드 중심
TEST_QUERIES: list[tuple[str, str]] = [
    ("수문장 교대식", "경복궁"),
    ("반가사유상", "국립중앙박물관"),
    ("경복궁 입장료", "경복궁"),
    ("후원 부용지 연경당", "창덕궁"),
    ("성수동 카페거리", "서울숲"),
]


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].replace(".txt", "")


def retrieve(client, kb_id: str, query: str, search_type: str) -> list[tuple[str, float]]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
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


def rank_of(results: list[tuple[str, float]], target: str) -> int | None:
    for i, (n, _) in enumerate(results, 1):
        if n == target:
            return i
    return None


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)

    improved = 0
    identical = 0

    for query, expected in TEST_QUERIES:
        sem = retrieve(client, kb_id, query, "SEMANTIC")
        hyb = retrieve(client, kb_id, query, "HYBRID")

        sem_rank = rank_of(sem, expected)
        hyb_rank = rank_of(hyb, expected)

        print(f"\n{'=' * 70}")
        print(f"질의: {query!r}   (기대 문서: {expected})")
        print("-" * 70)
        print("  [SEMANTIC]")
        for i, (n, s) in enumerate(sem, 1):
            mark = " <--" if n == expected else ""
            print(f"    {i}. {n:14s} {s}{mark}")
        print("  [HYBRID]")
        for i, (n, s) in enumerate(hyb, 1):
            mark = " <--" if n == expected else ""
            print(f"    {i}. {n:14s} {s}{mark}")

        if sem == hyb:
            identical += 1
            verdict = "두 방식 결과 동일 (시맨틱만으로 충분히 잡히는 질의)"
        elif hyb_rank is not None and (sem_rank is None or hyb_rank < sem_rank):
            improved += 1
            verdict = f"HYBRID 개선: 순위 {sem_rank} -> {hyb_rank}"
        else:
            verdict = f"순위 변화 있음 (SEM={sem_rank}, HYB={hyb_rank})"
        print(f"  => {verdict}")

    print(f"\n{'=' * 70}")
    print("정리")
    print(f"  HYBRID가 정답 문서 순위를 끌어올린 질의 : {improved}건")
    print(f"  두 방식이 동일한 결과를 낸 질의         : {identical}건")
    print(f"  전체 테스트 질의                       : {len(TEST_QUERIES)}건")
    print("\n  하이브리드는 문서 본문의 고유 키워드가 질의에 포함될 때")
    print("  키워드 매칭 점수가 더해져 해당 문서를 상위로 올린다.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
