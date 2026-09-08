# 02_hybrid_search.py — SEMANTIC vs HYBRID 비교
import os

import boto3

REGION = "us-west-2"
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

def search(query, search_type, top_k=3):
    resp = agent_rt.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": top_k,
                # 💡: retrieve의 검색 방식 필드는 overrideSearchType (SEMANTIC | HYBRID)
                "overrideSearchType": search_type,
            }
        },
    )
    return resp["retrievalResults"]

question = "트라토리아 벨라 메뉴 가격"

for search_type in ("SEMANTIC", "HYBRID"):
    print(f"\n=== {search_type} ===")
    for i, r in enumerate(search(question, search_type), 1):
        print(f"{i}. score={r['score']:.4f} | {r['content']['text'][:50]}")