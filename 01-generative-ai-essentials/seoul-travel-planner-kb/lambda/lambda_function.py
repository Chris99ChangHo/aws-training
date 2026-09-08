"""
lambda_function.py

S3 guides/ 프리픽스에 객체가 생성/삭제되면 Bedrock Knowledge Base의
데이터 소스 동기화(ingestion job)를 자동으로 시작한다.

S3 이벤트 알림 -> 이 Lambda -> bedrock-agent.start_ingestion_job

환경 변수:
    KB_ID          : Knowledge Base ID
    DATA_SOURCE_ID : 데이터 소스 ID

이미 진행 중인 ingestion job이 있으면 새로 시작하지 않는다. Bedrock은
데이터 소스당 동시에 하나의 ingestion job만 허용하므로, 여러 파일이
한꺼번에 업로드되어 이벤트가 여러 번 발생해도 중복 실행되지 않도록 한다.
"""

from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
KB_ID = os.environ["KB_ID"]
DATA_SOURCE_ID = os.environ["DATA_SOURCE_ID"]

# 진행 중으로 간주할 상태
IN_FLIGHT = ("STARTING", "IN_PROGRESS")

agent = boto3.client("bedrock-agent", region_name=REGION)


def has_running_job() -> str | None:
    """진행 중인 ingestion job이 있으면 그 ID를 반환한다."""
    for status in IN_FLIGHT:
        resp = agent.list_ingestion_jobs(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
            filters=[{"attribute": "STATUS", "operator": "EQ", "values": [status]}],
            maxResults=1,
        )
        jobs = resp.get("ingestionJobSummaries", [])
        if jobs:
            return jobs[0]["ingestionJobId"]
    return None


def lambda_handler(event, context):  # noqa: ANN001, ANN201
    # 어떤 객체 때문에 트리거됐는지 로깅
    changed = []
    for record in event.get("Records", []):
        name = record.get("eventName", "?")
        key = record.get("s3", {}).get("object", {}).get("key", "?")
        changed.append(f"{name}:{key}")
    logger.info("S3 이벤트 수신: %s", changed or event)

    running = has_running_job()
    if running:
        logger.info("이미 진행 중인 ingestion job(%s)이 있어 건너뜁니다.", running)
        return {
            "statusCode": 200,
            "skipped": True,
            "runningJobId": running,
            "triggeredBy": changed,
        }

    try:
        resp = agent.start_ingestion_job(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
            description="Auto sync triggered by S3 event",
        )
    except ClientError as err:
        code = err.response["Error"]["Code"]
        # 경쟁 조건으로 동시에 시작된 경우도 정상 처리
        if code == "ConflictException":
            logger.info("동시 실행 충돌 - 다른 job이 이미 시작됨")
            return {"statusCode": 200, "skipped": True, "reason": "conflict"}
        logger.error("ingestion job 시작 실패: %s", err)
        raise

    job_id = resp["ingestionJob"]["ingestionJobId"]
    logger.info("ingestion job 시작: %s", job_id)

    return {
        "statusCode": 200,
        "skipped": False,
        "ingestionJobId": job_id,
        "triggeredBy": changed,
    }
