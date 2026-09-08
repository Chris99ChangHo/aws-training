#!/usr/bin/env python3
"""이 실습이 만든 AWS 리소스를 삭제한다.

기본은 **dry-run**이다. 무엇을 지울지 출력하고 아무것도 지우지 않는다.
실제로 지우려면 `--delete`를 붙인다.

대상은 `kb_info.json`에 기록된 것과, 그것으로 API를 조회해 얻은 것뿐이다.
이름을 추측해서 지우지 않는다 — 같은 계정의 다른 리소스를 건드릴 수 있다.

삭제 순서에 의미가 있다. 참조하는 쪽을 먼저 지운다:
    데이터 소스 -> Knowledge Base -> OpenSearch 컬렉션
    -> 접근/보안 정책 -> S3 객체·버킷 -> IAM 역할

이 실습에는 자동 동기화 Lambda가 없다(seoul-travel-planner-kb에만 있다).

사용법:
    python3 cleanup.py            삭제 대상만 출력
    python3 cleanup.py --delete   실제 삭제

종료 코드:
    0  완료 (dry-run 포함)
    1  일부 삭제 실패 (출력에 어떤 것이 남았는지 표시)
    2  kb_info.json이 없어 대상을 특정할 수 없음
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

INFO_PATH = Path(__file__).parent / "kb_info.json"

failures: list[str] = []


def log(msg: str) -> None:
    """진행 상황을 stdout에 출력한다."""
    print(msg)


def plan(dry: bool, what: str) -> None:
    """무엇을 할지 한 줄로 알린다."""
    log(f"  {'[dry-run] 삭제 예정' if dry else '[삭제]'} {what}")


def absent(err: ClientError) -> bool:
    """이미 없는 리소스에 대한 오류인지 판정한다.

    멱등성을 위해 필요하다. 스크립트를 두 번 돌려도 두 번째가 실패로
    끝나면 "정리가 안 됐다"와 구분할 수 없다.
    """
    code = err.response.get("Error", {}).get("Code", "")
    return code in {
        "ResourceNotFoundException",
        "ResourceNotFound",
        "NoSuchEntity",
        "NoSuchBucket",
        "NotFoundException",
        "ValidationException",
        "404",
    }


def exists(label: str, probe: Any) -> bool:
    """리소스가 실제로 있는지 확인한다.

    dry-run이 존재하지 않는 것까지 "삭제 예정"으로 출력하면 계획이 아니라
    추측이 된다. 읽기 호출이므로 dry-run에서도 안전하다.
    """
    try:
        probe()
        return True
    except ClientError as err:
        if absent(err):
            log(f"      이미 없음: {label}")
            return False
        raise


def attempt(label: str, fn: Any, dry: bool) -> None:
    """삭제를 시도하고 실패를 모아 둔다. 예외를 삼키지 않는다."""
    plan(dry, label)
    if dry:
        return
    try:
        fn()
    except ClientError as err:
        if absent(err):
            log(f"      이미 없음: {label}")
            return
        failures.append(f"{label}: {err}")
        log(f"      실패: {err}")


def load_info() -> dict[str, Any] | None:
    """kb_info.json을 읽는다. 없으면 None."""
    if not INFO_PATH.exists():
        return None
    try:
        return json.loads(INFO_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        log(f"kb_info.json을 읽을 수 없습니다: {err}")
        return None


def kb_role_arn(bedrock: Any, kb_id: str) -> str | None:
    """Knowledge Base가 쓰는 실행 역할 ARN을 API에서 조회한다.

    역할 이름을 상수로 추측하지 않고 KB가 실제로 참조하는 값을 쓴다. KB를
    지우고 나면 조회할 수 없으므로 반드시 먼저 호출한다.
    """
    try:
        kb = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)
        return kb["knowledgeBase"].get("roleArn")
    except ClientError:
        return None


def delete_s3(s3: Any, bucket: str, dry: bool) -> None:
    """버킷의 모든 객체(버전 포함)와 버킷 자체를 지운다."""
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as err:
        if absent(err):
            log(f"      이미 없음: S3 버킷 {bucket}")
            return
        raise

    if not dry:
        paginator = s3.get_paginator("list_object_versions")
        batch: list[dict[str, str]] = []
        for page in paginator.paginate(Bucket=bucket):
            for key in ("Versions", "DeleteMarkers"):
                for obj in page.get(key, []):
                    batch.append({"Key": obj["Key"], "VersionId": obj["VersionId"]})
                    if len(batch) == 1000:
                        s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})
                        batch = []
        if batch:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})

    attempt(f"S3 버킷 {bucket}", lambda: s3.delete_bucket(Bucket=bucket), dry)


def delete_role(iam: Any, role_name: str, dry: bool) -> None:
    """인라인·연결 정책을 떼고 역할을 지운다.

    정책이 붙어 있으면 DeleteRole이 거부된다. 순서가 있는 삭제다.
    """
    try:
        for pol in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
            attempt(
                f"인라인 정책 {role_name}/{pol}",
                lambda p=pol: iam.delete_role_policy(RoleName=role_name, PolicyName=p),
                dry,
            )
        for att in iam.list_attached_role_policies(RoleName=role_name)[
            "AttachedPolicies"
        ]:
            attempt(
                f"연결 정책 해제 {role_name}/{att['PolicyName']}",
                lambda a=att: iam.detach_role_policy(
                    RoleName=role_name, PolicyArn=a["PolicyArn"]
                ),
                dry,
            )
    except ClientError as err:
        if absent(err):
            log(f"      이미 없음: IAM 역할 {role_name}")
            return
        raise
    attempt(f"IAM 역할 {role_name}", lambda: iam.delete_role(RoleName=role_name), dry)


def delete_collection(aoss: Any, name: str, dry: bool) -> None:
    """OpenSearch Serverless 컬렉션과 그에 딸린 정책을 지운다.

    컬렉션이 남아 있는 동안은 정책을 지울 수 없으므로 컬렉션이 사라질 때까지
    기다린다. 무한 대기하지 않도록 상한을 둔다.
    """
    try:
        found = aoss.batch_get_collection(names=[name])["collectionDetails"]
    except ClientError as err:
        if absent(err):
            found = []
        else:
            raise

    if found:
        cid = found[0]["id"]
        attempt(f"OpenSearch 컬렉션 {name}", lambda: aoss.delete_collection(id=cid), dry)
        if not dry:
            for _ in range(60):  # 최대 5분
                remaining = aoss.batch_get_collection(names=[name])["collectionDetails"]
                if not remaining:
                    break
                time.sleep(5)
            else:
                failures.append(f"컬렉션 {name}이 5분 안에 삭제되지 않았습니다")
    else:
        log(f"      이미 없음: OpenSearch 컬렉션 {name}")

    for kind, lister, deleter in (
        ("data", aoss.list_access_policies, aoss.delete_access_policy),
        ("encryption", aoss.list_security_policies, aoss.delete_security_policy),
        ("network", aoss.list_security_policies, aoss.delete_security_policy),
    ):
        try:
            if kind == "data":
                items = lister(type=kind)["accessPolicySummaries"]
            else:
                items = lister(type=kind)["securityPolicySummaries"]
        except ClientError:
            continue
        for item in items:
            if name not in item["name"]:
                continue
            attempt(
                f"{kind} 정책 {item['name']}",
                lambda i=item, k=kind, d=deleter: d(name=i["name"], type=k),
                dry,
            )


def main() -> int:
    """삭제 계획을 세우고 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="실제로 삭제한다. 생략하면 대상만 출력한다.",
    )
    args = parser.parse_args()
    dry = not args.delete

    info = load_info()
    if info is None:
        log("kb_info.json이 없습니다. 지울 대상을 특정할 수 없어 중단합니다.")
        log("이미 정리됐거나 setup을 실행하지 않은 상태입니다.")
        return 2

    region = info["region"]
    log(f"리전: {region}   모드: {'dry-run' if dry else '실제 삭제'}\n")

    bedrock = boto3.client("bedrock-agent", region_name=region)
    aoss = boto3.client("opensearchserverless", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    iam = boto3.client("iam")

    kb_id = info.get("knowledgeBaseId")
    role_arn = kb_role_arn(bedrock, kb_id) if kb_id else None

    bucket = info.get("bucket")

    log("1. Knowledge Base")
    ds_id = info.get("dataSourceId")
    kb_present = bool(kb_id) and exists(
        f"Knowledge Base {kb_id}",
        lambda: bedrock.get_knowledge_base(knowledgeBaseId=kb_id),
    )
    if kb_present and ds_id:
        attempt(
            f"데이터 소스 {ds_id}",
            lambda: bedrock.delete_data_source(
                knowledgeBaseId=kb_id, dataSourceId=ds_id
            ),
            dry,
        )
    if kb_present:
        attempt(
            f"Knowledge Base {kb_id}",
            lambda: bedrock.delete_knowledge_base(knowledgeBaseId=kb_id),
            dry,
        )

    log("\n2. OpenSearch Serverless")
    collection = info.get("collectionName")
    if collection:
        delete_collection(aoss, collection, dry)

    log("\n3. S3")
    if bucket:
        delete_s3(s3, bucket, dry)   # 내부에서 존재를 다시 확인한다

    log("\n4. IAM 실행 역할")
    if role_arn:
        delete_role(iam, role_arn.rsplit("/", 1)[-1], dry)
    else:
        log("      KB에서 역할 ARN을 조회하지 못했습니다. 콘솔에서 확인하세요.")

    log("")
    if dry:
        log("dry-run이었습니다. 실제로 지우려면: python3 cleanup.py --delete")
        return 0

    if failures:
        log(f"{len(failures)}건이 남았습니다:")
        for f in failures:
            log(f"  - {f}")
        log("콘솔에서 확인하세요. 남은 리소스는 계속 과금됩니다.")
        return 1

    log("정리 완료. kb_info.json은 남겨둡니다(재실행 시 이미 없음으로 처리).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
