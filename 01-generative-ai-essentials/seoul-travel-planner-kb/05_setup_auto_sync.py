"""
08_setup_auto_sync.py

S3에 새 데이터가 들어오면 Bedrock Knowledge Base가 자동으로 동기화되도록
이벤트 기반 파이프라인을 구축한다.

구성 요소:
  1. Lambda 실행용 IAM 역할 (+ CloudWatch Logs, bedrock-agent 권한)
  2. Lambda 함수 (lambda/lambda_function.py 를 zip으로 패키징)
  3. Lambda resource policy (S3가 이 함수를 호출할 수 있도록 허용)
  4. S3 버킷 이벤트 알림 (guides/ 프리픽스의 ObjectCreated/ObjectRemoved)

멱등하게 동작하므로 여러 번 실행해도 안전하다.

사용법:
    python 08_setup_auto_sync.py
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "travel-kb-auto-sync"
ROLE_NAME = "travel-kb-auto-sync-lambda-role"
LAMBDA_SRC = Path(__file__).parent / "lambda" / "lambda_function.py"
PREFIX = "guides/"


def log(msg: str) -> None:
    print(msg, flush=True)


def build_zip() -> bytes:
    """Lambda 배포 패키지(zip)를 메모리에 만든다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", LAMBDA_SRC.read_text(encoding="utf-8"))
    return buf.getvalue()


def ensure_role(iam, account_id: str, kb_id: str, ds_id: str) -> str:
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        resp = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Execution role for travel-planner-kb auto sync Lambda",
        )
        role_arn = resp["Role"]["Arn"]
        log(f"[iam] 역할 생성: {ROLE_NAME}")
        created = True
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        log(f"[iam] 기존 역할 사용: {ROLE_NAME}")
        created = False

    kb_arn = f"arn:aws:bedrock:{REGION}:{account_id}:knowledge-base/{kb_id}"
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Logs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": f"arn:aws:logs:{REGION}:{account_id}:*",
            },
            {
                "Sid": "StartAndInspectIngestion",
                "Effect": "Allow",
                "Action": [
                    "bedrock:StartIngestionJob",
                    "bedrock:ListIngestionJobs",
                    "bedrock:GetIngestionJob",
                ],
                "Resource": kb_arn,
            },
        ],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="AutoSyncPolicy",
        PolicyDocument=json.dumps(policy),
    )
    log("[iam] 인라인 정책 적용 완료")

    if created:
        # 새로 만든 역할은 Lambda가 인식할 때까지 전파 시간이 필요하다.
        log("[iam] 역할 전파 대기(15초)...")
        time.sleep(15)

    return role_arn


def ensure_function(lam, role_arn: str, kb_id: str, ds_id: str) -> str:
    code = build_zip()
    env = {"Variables": {"KB_ID": kb_id, "DATA_SOURCE_ID": ds_id}}

    try:
        resp = lam.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": code},
            Timeout=60,
            MemorySize=256,
            Environment=env,
            Description="Auto-trigger Bedrock KB ingestion on S3 guides/ changes",
        )
        arn = resp["FunctionArn"]
        log(f"[lambda] 함수 생성: {FUNCTION_NAME}")
    except lam.exceptions.ResourceConflictException:
        log(f"[lambda] 기존 함수 갱신: {FUNCTION_NAME}")
        lam.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=code)
        _wait_updated(lam)
        lam.update_function_configuration(
            FunctionName=FUNCTION_NAME, Environment=env, Role=role_arn, Timeout=60
        )
        _wait_updated(lam)
        arn = lam.get_function(FunctionName=FUNCTION_NAME)["Configuration"]["FunctionArn"]

    # 함수가 Active 상태가 될 때까지 대기
    for _ in range(30):
        state = lam.get_function(FunctionName=FUNCTION_NAME)["Configuration"]["State"]
        if state == "Active":
            break
        time.sleep(2)

    return arn


def _wait_updated(lam) -> None:
    for _ in range(30):
        cfg = lam.get_function(FunctionName=FUNCTION_NAME)["Configuration"]
        if cfg.get("LastUpdateStatus") != "InProgress":
            return
        time.sleep(2)


def allow_s3_invoke(lam, account_id: str, bucket: str) -> None:
    """S3가 Lambda를 호출할 수 있도록 resource policy를 추가한다."""
    try:
        lam.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="AllowS3Invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{bucket}",
            SourceAccount=account_id,
        )
        log("[lambda] S3 호출 권한 추가")
    except lam.exceptions.ResourceConflictException:
        log("[lambda] S3 호출 권한 이미 존재")


def configure_notification(s3, bucket: str, function_arn: str) -> None:
    """guides/ 프리픽스의 객체 생성/삭제 이벤트를 Lambda로 보낸다."""
    config = {
        "LambdaFunctionConfigurations": [
            {
                "Id": "travel-kb-guides-sync",
                "LambdaFunctionArn": function_arn,
                "Events": ["s3:ObjectCreated:*", "s3:ObjectRemoved:*"],
                "Filter": {
                    "Key": {
                        "FilterRules": [{"Name": "prefix", "Value": PREFIX}]
                    }
                },
            }
        ]
    }

    # 권한 전파 지연으로 실패할 수 있어 재시도
    last_err: Exception | None = None
    for attempt in range(1, 7):
        try:
            s3.put_bucket_notification_configuration(
                Bucket=bucket, NotificationConfiguration=config
            )
            log(f"[s3] 이벤트 알림 설정 완료 (prefix={PREFIX})")
            return
        except ClientError as err:
            last_err = err
            log(f"[s3] 시도 {attempt}/6 실패, 재시도... ({err.response['Error']['Code']})")
            time.sleep(5)
    raise RuntimeError(f"S3 이벤트 알림 설정 실패: {last_err}")


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        info = json.load(fh)
    kb_id = info["knowledgeBaseId"]
    ds_id = info["dataSourceId"]
    bucket = info["bucket"]

    session = boto3.session.Session(region_name=REGION)
    account_id = session.client("sts").get_caller_identity()["Account"]
    iam = session.client("iam")
    lam = session.client("lambda")
    s3 = session.client("s3")

    log(f"[info] KB={kb_id} DS={ds_id} bucket={bucket}")

    role_arn = ensure_role(iam, account_id, kb_id, ds_id)
    function_arn = ensure_function(lam, role_arn, kb_id, ds_id)
    allow_s3_invoke(lam, account_id, bucket)
    configure_notification(s3, bucket, function_arn)

    log("\n" + "=" * 60)
    log("✅ 자동 동기화 파이프라인 구축 완료")
    log(f"  Lambda      : {FUNCTION_NAME}")
    log(f"  IAM 역할    : {ROLE_NAME}")
    log(f"  트리거      : s3://{bucket}/{PREFIX} (ObjectCreated, ObjectRemoved)")
    log(f"  동작        : 이벤트 발생 -> start_ingestion_job 자동 실행")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
