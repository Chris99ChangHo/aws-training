"""
02_create_kb.py

Bedrock Knowledge Base(travel-planner-kb)를 생성하고 S3 데이터 소스를
동기화한다.

콘솔의 "Quick create" 벡터 스토어가 자동으로 처리하는 작업을 API로 직접
수행한다:
  1. KB 실행용 IAM 역할 + 인라인 정책
  2. OpenSearch Serverless 암호화/네트워크/데이터 액세스 정책
  3. OpenSearch Serverless 벡터 컬렉션 (VECTORSEARCH)
  4. 벡터 인덱스 (knn_vector, 1024 차원 = Titan Embed V2)
  5. Knowledge Base
  6. S3 데이터 소스 (inclusionPrefixes=["guides/"])
  7. Ingestion job 시작 후 COMPLETE까지 폴링

완료 기준: KB 상태 ACTIVE + 동기화 COMPLETE

사용법:
    python 02_create_kb.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

REGION = "us-east-1"

KB_NAME = "travel-planner-kb"
DATA_SOURCE_NAME = "travel-guides-s3"
COLLECTION_NAME = "travel-planner-kb"
INDEX_NAME = "bedrock-knowledge-base-default-index"
ROLE_NAME = "AmazonBedrockExecutionRoleForKB-travel-planner"

EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSION = 1024

S3_PREFIX = "guides/"
PREFERRED_BUCKET = "travel-planner-kb-data"

# 벡터 인덱스 필드 매핑 (Bedrock KB 기본 규약)
VECTOR_FIELD = "bedrock-knowledge-base-default-vector"
TEXT_FIELD = "AMAZON_BEDROCK_TEXT_CHUNK"
METADATA_FIELD = "AMAZON_BEDROCK_METADATA"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- bucket


def resolve_bucket(s3, account_id: str) -> str:
    """01단계에서 업로드한 버킷을 찾는다."""
    for name in (PREFERRED_BUCKET, f"{PREFERRED_BUCKET}-{account_id}"):
        try:
            resp = s3.list_objects_v2(Bucket=name, Prefix=S3_PREFIX, MaxKeys=1)
        except ClientError:
            continue
        if resp.get("KeyCount", 0) > 0:
            log(f"[s3] 데이터 소스 버킷: {name}")
            return name
    raise RuntimeError(
        f"{S3_PREFIX} 아래 객체가 있는 버킷을 찾지 못했습니다. "
        "01_upload_data.py를 먼저 실행하세요."
    )


# ---------------------------------------------------------------- iam


def ensure_role(iam, account_id: str, bucket: str, collection_arn_pattern: str) -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                },
            }
        ],
    }

    try:
        resp = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Bedrock Knowledge Base execution role (travel-planner)",
        )
        role_arn = resp["Role"]["Arn"]
        log(f"[iam] 역할 생성: {ROLE_NAME}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        log(f"[iam] 기존 역할 사용: {ROLE_NAME}")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeEmbeddingModel",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/{EMBED_MODEL_ID}",
            },
            {
                "Sid": "ReadDataSource",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*",
                ],
                "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}},
            },
            {
                "Sid": "OpenSearchServerlessAccess",
                "Effect": "Allow",
                "Action": "aoss:APIAccessAll",
                "Resource": collection_arn_pattern,
            },
        ],
    }

    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="KBExecutionPolicy",
        PolicyDocument=json.dumps(policy),
    )
    log("[iam] 인라인 정책 적용 완료")
    return role_arn


# ---------------------------------------------------------------- aoss


def _put_policy(fn, kind: str, **kwargs) -> None:
    try:
        fn(**kwargs)
        log(f"[aoss] {kind} 정책 생성")
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConflictException":
            log(f"[aoss] {kind} 정책 이미 존재")
        else:
            raise


def ensure_collection(aoss, role_arn: str, caller_arn: str) -> tuple[str, str]:
    """AOSS 정책과 벡터 컬렉션을 생성하고 (collection_arn, endpoint)를 반환."""
    collection_res = [f"collection/{COLLECTION_NAME}"]

    _put_policy(
        aoss.create_security_policy,
        "암호화",
        name=f"{COLLECTION_NAME}-enc",
        type="encryption",
        policy=json.dumps(
            {"Rules": [{"ResourceType": "collection", "Resource": collection_res}],
             "AWSOwnedKey": True}
        ),
    )

    _put_policy(
        aoss.create_security_policy,
        "네트워크",
        name=f"{COLLECTION_NAME}-net",
        type="network",
        policy=json.dumps(
            [
                {
                    "Rules": [
                        {"ResourceType": "collection", "Resource": collection_res},
                        {"ResourceType": "dashboard", "Resource": collection_res},
                    ],
                    "AllowFromPublic": True,
                }
            ]
        ),
    )

    _put_policy(
        aoss.create_access_policy,
        "데이터 액세스",
        name=f"{COLLECTION_NAME}-access",
        type="data",
        policy=json.dumps(
            [
                {
                    "Rules": [
                        {
                            "ResourceType": "index",
                            "Resource": [f"index/{COLLECTION_NAME}/*"],
                            "Permission": ["aoss:*"],
                        },
                        {
                            "ResourceType": "collection",
                            "Resource": collection_res,
                            "Permission": ["aoss:*"],
                        },
                    ],
                    "Principal": [role_arn, caller_arn],
                }
            ]
        ),
    )

    try:
        aoss.create_collection(name=COLLECTION_NAME, type="VECTORSEARCH")
        log(f"[aoss] 컬렉션 생성 요청: {COLLECTION_NAME}")
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConflictException":
            log(f"[aoss] 컬렉션 이미 존재: {COLLECTION_NAME}")
        else:
            raise

    log("[aoss] 컬렉션 ACTIVE 대기 중...")
    deadline = time.time() + 900
    while time.time() < deadline:
        detail = aoss.batch_get_collection(names=[COLLECTION_NAME])
        items = detail.get("collectionDetails", [])
        if items:
            status = items[0]["status"]
            if status == "ACTIVE":
                arn = items[0]["arn"]
                endpoint = items[0]["collectionEndpoint"]
                log(f"[aoss] ACTIVE: {endpoint}")
                return arn, endpoint
            if status == "FAILED":
                raise RuntimeError("AOSS 컬렉션 생성 실패")
        time.sleep(15)
    raise TimeoutError("AOSS 컬렉션이 ACTIVE 되지 않았습니다")


def ensure_index(session, endpoint: str) -> None:
    """Bedrock KB가 요구하는 knn_vector 인덱스를 생성한다."""
    host = endpoint.replace("https://", "")
    auth = AWSV4SignerAuth(session.get_credentials(), REGION, "aoss")
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=300,
    )

    body = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                VECTOR_FIELD: {
                    "type": "knn_vector",
                    "dimension": EMBED_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "l2",
                        "parameters": {"ef_construction": 512, "m": 16},
                    },
                },
                TEXT_FIELD: {"type": "text"},
                METADATA_FIELD: {"type": "text", "index": False},
            }
        },
    }

    # 데이터 액세스 정책 전파에 시간이 걸릴 수 있어 재시도한다.
    last_err: Exception | None = None
    for attempt in range(1, 13):
        try:
            if client.indices.exists(index=INDEX_NAME):
                log(f"[index] 이미 존재: {INDEX_NAME}")
                return
            client.indices.create(index=INDEX_NAME, body=body)
            log(f"[index] 생성 완료: {INDEX_NAME}")
            # 인덱스가 KB 생성 시점에 조회 가능하도록 잠시 대기
            time.sleep(45)
            return
        except Exception as err:  # noqa: BLE001 - AOSS 권한 전파 대기
            last_err = err
            log(f"[index] 시도 {attempt}/12 실패, 재시도... ({type(err).__name__})")
            time.sleep(15)
    raise RuntimeError(f"인덱스 생성 실패: {last_err}")


# ---------------------------------------------------------------- kb


def ensure_kb(agent, role_arn: str, collection_arn: str) -> str:
    for kb in agent.list_knowledge_bases().get("knowledgeBaseSummaries", []):
        if kb["name"] == KB_NAME:
            log(f"[kb] 기존 KB 사용: {kb['knowledgeBaseId']}")
            return kb["knowledgeBaseId"]

    last_err: Exception | None = None
    for attempt in range(1, 9):
        try:
            resp = agent.create_knowledge_base(
                name=KB_NAME,
                description="서울 관광지 가이드 기반 여행 플래너 지식 베이스",
                roleArn=role_arn,
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": (
                            f"arn:aws:bedrock:{REGION}::foundation-model/{EMBED_MODEL_ID}"
                        )
                    },
                },
                storageConfiguration={
                    "type": "OPENSEARCH_SERVERLESS",
                    "opensearchServerlessConfiguration": {
                        "collectionArn": collection_arn,
                        "vectorIndexName": INDEX_NAME,
                        "fieldMapping": {
                            "vectorField": VECTOR_FIELD,
                            "textField": TEXT_FIELD,
                            "metadataField": METADATA_FIELD,
                        },
                    },
                },
            )
            kb_id = resp["knowledgeBase"]["knowledgeBaseId"]
            log(f"[kb] 생성 완료: {kb_id}")
            return kb_id
        except ClientError as err:
            # IAM/인덱스 전파 지연으로 ValidationException이 날 수 있다.
            last_err = err
            log(f"[kb] 시도 {attempt}/8 실패, 재시도... ({err.response['Error']['Code']})")
            time.sleep(20)
    raise RuntimeError(f"KB 생성 실패: {last_err}")


def wait_kb_active(agent, kb_id: str) -> None:
    deadline = time.time() + 600
    while time.time() < deadline:
        status = agent.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
        if status == "ACTIVE":
            log(f"[kb] 상태: ACTIVE")
            return
        if status == "FAILED":
            raise RuntimeError("KB 생성 실패 상태")
        log(f"[kb] 상태: {status} ... 대기")
        time.sleep(10)
    raise TimeoutError("KB가 ACTIVE 되지 않았습니다")


def ensure_data_source(agent, kb_id: str, bucket: str, account_id: str) -> str:
    for ds in agent.list_data_sources(knowledgeBaseId=kb_id).get(
        "dataSourceSummaries", []
    ):
        if ds["name"] == DATA_SOURCE_NAME:
            log(f"[ds] 기존 데이터 소스 사용: {ds['dataSourceId']}")
            return ds["dataSourceId"]

    resp = agent.create_data_source(
        knowledgeBaseId=kb_id,
        name=DATA_SOURCE_NAME,
        description="S3 guides/ 프리픽스의 서울 관광지 가이드 문서",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{bucket}",
                "bucketOwnerAccountId": account_id,
                "inclusionPrefixes": [S3_PREFIX],
            },
        },
        vectorIngestionConfiguration={
            "chunkingConfiguration": {
                "chunkingStrategy": "FIXED_SIZE",
                "fixedSizeChunkingConfiguration": {
                    "maxTokens": 300,
                    "overlapPercentage": 20,
                },
            }
        },
    )
    ds_id = resp["dataSource"]["dataSourceId"]
    log(f"[ds] 데이터 소스 생성: {ds_id}")
    return ds_id


def sync(agent, kb_id: str, ds_id: str) -> dict:
    job = agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    job_id = job["ingestionJob"]["ingestionJobId"]
    log(f"[sync] Ingestion job 시작: {job_id}")

    deadline = time.time() + 1800
    while time.time() < deadline:
        jobs = agent.list_ingestion_jobs(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            filters=[
                {"attribute": "STATUS", "operator": "EQ", "values": ["COMPLETE"]}
            ],
        )
        done = [
            j
            for j in jobs.get("ingestionJobSummaries", [])
            if j["ingestionJobId"] == job_id
        ]
        if done:
            log("[sync] 상태: COMPLETE")
            return agent.get_ingestion_job(
                knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
            )["ingestionJob"]

        detail = agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        status = detail["status"]
        if status == "FAILED":
            raise RuntimeError(f"동기화 실패: {detail.get('failureReasons')}")
        log(f"[sync] 상태: {status} ... 대기")
        time.sleep(15)
    raise TimeoutError("Ingestion job이 완료되지 않았습니다")


# ---------------------------------------------------------------- main


def main() -> int:
    session = boto3.session.Session(region_name=REGION)
    sts = session.client("sts")
    s3 = session.client("s3")
    iam = session.client("iam")
    aoss = session.client("opensearchserverless")
    agent = session.client("bedrock-agent")

    ident = sts.get_caller_identity()
    account_id = ident["Account"]
    caller_arn = ident["Arn"]
    # assumed-role ARN을 데이터 액세스 정책용 role ARN 형태로 변환
    if ":assumed-role/" in caller_arn:
        role_part = caller_arn.split(":assumed-role/")[1].split("/")[0]
        caller_arn = f"arn:aws:iam::{account_id}:role/{role_part}"

    bucket = resolve_bucket(s3, account_id)

    role_arn = ensure_role(
        iam,
        account_id,
        bucket,
        f"arn:aws:aoss:{REGION}:{account_id}:collection/*",
    )
    # IAM 역할 전파 대기
    time.sleep(10)

    collection_arn, endpoint = ensure_collection(aoss, role_arn, caller_arn)
    ensure_index(session, endpoint)

    kb_id = ensure_kb(agent, role_arn, collection_arn)
    wait_kb_active(agent, kb_id)

    ds_id = ensure_data_source(agent, kb_id, bucket, account_id)
    job = sync(agent, kb_id, ds_id)

    stats = job.get("statistics", {})
    log("\n" + "=" * 60)
    log("✅ 완료")
    log(f"  KB 이름        : {KB_NAME}")
    log(f"  KB ID          : {kb_id}")
    log(f"  데이터 소스 ID : {ds_id}")
    log(f"  S3 URI         : s3://{bucket}/{S3_PREFIX}")
    log(f"  임베딩 모델    : {EMBED_MODEL_ID}")
    log(f"  벡터 스토어    : OpenSearch Serverless / {COLLECTION_NAME}")
    log(f"  동기화 상태    : COMPLETE")
    log(f"  스캔 문서      : {stats.get('numberOfDocumentsScanned')}")
    log(f"  인덱싱 완료    : {stats.get('numberOfNewDocumentsIndexed')}")
    log(f"  실패 문서      : {stats.get('numberOfDocumentsFailed')}")
    log("=" * 60)

    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "knowledgeBaseId": kb_id,
                "dataSourceId": ds_id,
                "bucket": bucket,
                "prefix": S3_PREFIX,
                "region": REGION,
                "collectionName": COLLECTION_NAME,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )
    log("[out] kb_info.json 저장 (다음 단계에서 사용)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ClientError, RuntimeError, TimeoutError) as exc:
        print(f"\n❌ 오류: {exc}", file=sys.stderr)
        raise SystemExit(1)
