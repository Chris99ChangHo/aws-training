# 02_create_kb.py — 콘솔에서 만든 KB의 데이터 소스를 동기화
import os
import time
import boto3

# 콘솔 KB 상세 페이지 상단의 Knowledge base ID를 환경변수로 주입: export KNOWLEDGE_BASE_ID=...
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "<YOUR_KNOWLEDGE_BASE_ID>")

agent = boto3.client("bedrock-agent", region_name="us-west-2")

#      다시 호출하면 같은 프리픽스가 이중 인덱싱되므로 조회만 합니다
ds = agent.list_data_sources(knowledgeBaseId=KNOWLEDGE_BASE_ID)["dataSourceSummaries"][0]
print(f"데이터 소스: {ds['name']} ({ds['dataSourceId']})")

# 동기화 시작
job = agent.start_ingestion_job(
    knowledgeBaseId=KNOWLEDGE_BASE_ID,
    dataSourceId=ds["dataSourceId"],
)
job_id = job["ingestionJob"]["ingestionJobId"]

while True:
    status = agent.get_ingestion_job(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        dataSourceId=ds["dataSourceId"],
        ingestionJobId=job_id,
    )["ingestionJob"]["status"]
    print(f"상태: {status}")
    if status in ("COMPLETE", "FAILED"):
        break
    time.sleep(15)