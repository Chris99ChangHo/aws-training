# 03_rerank_search.py — 리랭킹 전/후 순위 비교
import os

import boto3

REGION = "us-west-2"
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")
# 💡: us-west-2에서 제공되는 Bedrock 리랭커는 Cohere Rerank 3.5
RERANK_MODEL_ARN = f"arn:aws:bedrock:{REGION}::foundation-model/cohere.rerank-v3-5:0"

agent_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)

def search(query, rerank=False, top_k=5):
    vector_cfg = {"numberOfResults": top_k, "overrideSearchType": "HYBRID"}
    if rerank:
        vector_cfg["rerankingConfiguration"] = {
            "type": "BEDROCK_RERANKING_MODEL",
            "bedrockRerankingConfiguration": {
                "modelConfiguration": {"modelArn": RERANK_MODEL_ARN},
                "numberOfRerankedResults": top_k,
            },
        }
    resp = agent_rt.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": vector_cfg},
    )
    return resp["retrievalResults"]

question = "2명이서 데이트하기 좋은 곳 추천해 주세요. 예산은 1인 5만원이에요."

before = search(question)
after = search(question, rerank=True)

print("=== 리랭킹 전 / 후 ===")
for i in range(len(before)):
    b = before[i]["content"]["text"][:30].replace("\n", " ")
    a = after[i]["content"]["text"][:30].replace("\n", " ")
    print(f"{i + 1}. {b}  →  {a}")