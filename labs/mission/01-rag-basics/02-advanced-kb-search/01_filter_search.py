# 01_filter_search.py — 메타데이터 필터 전/후 비교
import os

import boto3

REGION = "us-west-2"
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

def search(query, kb_filter=None, top_k=5):
    # 💡: 검색 옵션은 전부 vectorSearchConfiguration 아래에 둡니다
    vector_cfg = {"numberOfResults": top_k}
    if kb_filter:
        vector_cfg["filter"] = kb_filter
    resp = agent_rt.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": vector_cfg},
    )
    return resp["retrievalResults"]

def show(title, results):
    print(f"\n=== {title} ===")
    for i, r in enumerate(results, 1):
        # 💡: .metadata.json의 커스텀 속성은 결과의 metadata 맵으로 돌아옵니다
        meta = r.get("metadata", {})
        print(f"{i}. [{meta.get('category', '-')}] {r['content']['text'][:50]}")

question = "추천 메뉴 알려주세요"

show("필터 없음", search(question))

korean_filter = {"equals": {"key": "category", "value": "한식"}}
show('category = "한식"', search(question, kb_filter=korean_filter))