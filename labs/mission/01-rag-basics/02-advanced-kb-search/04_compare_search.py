# 04_compare_search.py — 기본/필터/하이브리드/리랭킹 종합 비교
import os

import boto3

REGION = "us-west-2"
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")
RERANK_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/cohere.rerank-v3-5:0"

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

def search(query, extra_cfg):
    resp = agent_rt.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 3, **extra_cfg}
        },
    )
    return resp["retrievalResults"]

question = "회식하기 좋은 한식당 추천해 주세요"

configs = {
    "기본": {},
    "필터": {"filter": {"equals": {"key": "category", "value": "한식"}}},
    "하이브리드": {"overrideSearchType": "HYBRID"},
    "리랭킹": {
        "overrideSearchType": "HYBRID",
        "rerankingConfiguration": {
            "type": "BEDROCK_RERANKING_MODEL",
            "bedrockRerankingConfiguration": {
                "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                "numberOfRerankedResults": 3,
            },
        },
    },
}

print(f"질문: {question}\n")
print("| 설정 | 1순위 | 2순위 | 3순위 |")
print("|------|-------|-------|-------|")
for name, cfg in configs.items():
    row = [r["content"]["text"][:15].replace("\n", " ") for r in search(question, cfg)]
    print(f"| {name} | {' | '.join(row)} |")