"""
04_compare_all.py

동일 질문 "서울에서 반나절 역사 코스"로 4가지 설정의 검색 결과를 나란히
비교한다.

  1. 기본 검색   : 벡터 유사도만 (SEMANTIC)
  2. 메타데이터 필터 : category 에 "역사" 포함
  3. 하이브리드   : overrideSearchType=HYBRID
  4. 리랭킹      : Cohere Rerank v3.5 (막히면 LLM 리랭커 폴백)

사용법:
    python 04_compare_all.py
"""

from __future__ import annotations

import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
QUERY = "서울에서 반나절 역사 코스"

ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
RERANK_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/cohere.rerank-v3-5:0"

# 질문 의도(역사 체험)에 부합하는 관광지
HISTORY_RELATED = {"경복궁", "북촌한옥마을", "DMZ", "창덕궁", "국립중앙박물관"}

TOP_K = 3


def name_of(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].replace(".txt", "")


def dedupe(results: list[dict], score_key: str | None = None) -> list[tuple[str, float]]:
    """문서 단위로 최고 점수만 남기고 원래 순서를 유지한다."""
    best: dict[str, float] = {}
    order: list[str] = []
    for r in results:
        n = name_of(r["location"]["s3Location"]["uri"])
        raw = r.get(score_key) if score_key else r.get("score", 0.0)
        s = float(raw if raw is not None else 0.0)
        if n not in best:
            best[n] = s
            order.append(n)
        else:
            best[n] = max(best[n], s)
    return [(n, best[n]) for n in order]


def run(client, kb_id: str, cfg: dict) -> list[dict]:
    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": QUERY},
        retrievalConfiguration={"vectorSearchConfiguration": cfg},
    )
    return resp["retrievalResults"]


def print_table(results: dict[str, list[tuple[str, float]]]) -> None:
    labels = list(results.keys())
    rows = max(len(v) for v in results.values())
    col = 26

    header = "순위".ljust(5) + "".join(l.ljust(col) for l in labels)
    print(header)
    print("-" * len(header))

    for i in range(rows):
        row = f"{i + 1:<5}"
        for label in labels:
            items = results[label]
            if i < len(items):
                n, s = items[i]
                tag = "*" if n in HISTORY_RELATED else " "
                cell = f"{n}{tag}({s:.3f})"
            else:
                cell = "-"
            row += cell.ljust(col)
        print(row)
    print("\n(* = 역사 관련 관광지)")


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        kb_id = json.load(fh)["knowledgeBaseId"]

    client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    runtime = boto3.client("bedrock-runtime", region_name=REGION)

    print(f"질의: {QUERY!r}\n")

    results: dict[str, list[tuple[str, float]]] = {}

    # 1. 기본
    base_raw = run(client, kb_id, {"numberOfResults": 10, "overrideSearchType": "SEMANTIC"})
    results["1.기본검색"] = dedupe(base_raw)

    # 2. 필터
    results["2.필터(역사)"] = dedupe(
        run(
            client,
            kb_id,
            {
                "numberOfResults": 10,
                "filter": {"stringContains": {"key": "category", "value": "역사"}},
            },
        )
    )

    # 3. 하이브리드
    results["3.하이브리드"] = dedupe(
        run(client, kb_id, {"numberOfResults": 10, "overrideSearchType": "HYBRID"})
    )

    # 4. 리랭킹 (Cohere -> 실패 시 LLM 폴백)
    rerank_label = "4.리랭킹(Cohere)"
    try:
        rr = run(
            client,
            kb_id,
            {
                "numberOfResults": 10,
                "rerankingConfiguration": {
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "numberOfRerankedResults": 10,
                        "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                    },
                },
            },
        )
        results[rerank_label] = dedupe(rr)
    except ClientError as err:
        if "marketplace" in str(err).lower() or "AccessDenied" in str(err):
            print("[!] Cohere Rerank 차단 -> LLM 리랭커로 대체\n")
            import importlib
            import sys

            # 어느 디렉토리에서 실행하든 같은 폴더의 03_rerank_search.py를
            # 찾을 수 있도록 이 스크립트의 위치를 sys.path에 넣는다.
            script_dir = str(Path(__file__).parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            m = importlib.import_module("03_rerank_search")
            rr = m.llm_rerank(runtime, base_raw, query=QUERY)
            rerank_label = "4.리랭킹(LLM)"
            results[rerank_label] = dedupe(rr, score_key="_rerank_score")
        else:
            raise

    print_table(results)

    print(f"\n{'=' * 70}")
    print(f"상위 {TOP_K}개 중 역사 관련 관광지 비율")
    print("-" * 70)
    baseline = None
    for label, items in results.items():
        top = [n for n, _ in items[:TOP_K]]
        hits = len(set(top) & HISTORY_RELATED)
        if baseline is None:
            baseline = hits
        delta = hits - baseline
        sign = f"(기준)" if delta == 0 and label.startswith("1.") else f"({delta:+d})"
        print(f"  {label:18s} {hits}/{TOP_K} {sign:8s} {top}")

    print(f"\n{'=' * 70}")
    print("해석")
    print("  - 기본 검색: 역사 관련 문서와 무관 문서의 벡터 점수가 촘촘히 붙어")
    print("               순위가 뒤섞인다 (서울숲/남산타워가 상위 진입).")
    print("  - 필터     : 카테고리 조건으로 강제 선별해 정밀도가 가장 높지만,")
    print("               필터 밖 후보는 원천 배제된다.")
    print("  - 하이브리드: 질의에 문서 고유 키워드가 있을 때 재현율이 오른다.")
    print("               (일반적인 질의에서는 기본 검색과 큰 차이 없음)")
    print("  - 리랭킹   : 필터처럼 자르지 않으면서 질의 의도에 맞는 문서를")
    print("               상위로 재배치한다. 의미 기반 정렬에 가장 효과적.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
