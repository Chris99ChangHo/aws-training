"""
01_upload_data.py

서울 관광지 6곳의 가이드 문서(.txt)와 Bedrock Knowledge Base 메타데이터
(.metadata.json)를 S3에 업로드한다.

완료 기준: guides/ 프리픽스 아래 .txt 6개 + .metadata.json 6개 = 12개 객체.

사용법:
    python 01_upload_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
PREFERRED_BUCKET = "travel-planner-kb-data"
PREFIX = "guides/"

# 로컬 데이터 위치 (워크숍에서 제공된 파일을 그대로 사용)
DATA_ROOT = Path(__file__).parent / "travel-kb-ko"
DOCS_DIR = DATA_ROOT / "destinations"
META_DIR = DATA_ROOT / "metadata"

# 관광지 6곳. (문서 파일 stem, S3에 올릴 논리적 이름)
DESTINATIONS = [
    "경복궁",
    "남산타워",
    "북촌한옥마을",
    "광장시장",
    "이태원한남동",
    "DMZ",
]


def resolve_bucket(s3, sts) -> str:
    """사용할 버킷 이름을 결정하고, 없으면 생성한다.

    S3 버킷 이름은 전역적으로 고유해야 한다. 선호 이름이 다른 계정에서
    이미 점유된 경우 계정 ID를 접미사로 붙인 고유 이름으로 폴백한다.
    """
    candidates = [PREFERRED_BUCKET]
    account_id = sts.get_caller_identity()["Account"]
    candidates.append(f"{PREFERRED_BUCKET}-{account_id}")

    for name in candidates:
        # 이미 내 소유로 존재하는지 확인
        try:
            s3.head_bucket(Bucket=name)
            print(f"[bucket] 기존 버킷 사용: {name}")
            return name
        except ClientError as err:
            code = err.response["Error"]["Code"]
            # 403 = 존재하지만 내 소유가 아님 -> 다음 후보로
            if code in ("403", "AccessDenied"):
                print(f"[bucket] {name}: 접근 불가(타 계정 소유 가능) -> 다음 후보 시도")
                continue
            # 404 = 없음 -> 생성 시도
            if code not in ("404", "NoSuchBucket"):
                raise

        try:
            # us-east-1은 LocationConstraint를 지정하지 않는다.
            s3.create_bucket(Bucket=name)
            print(f"[bucket] 생성 완료: {name}")
            return name
        except ClientError as err:
            code = err.response["Error"]["Code"]
            if code == "BucketAlreadyOwnedByYou":
                print(f"[bucket] 이미 보유 중: {name}")
                return name
            if code in ("BucketAlreadyExists", "AccessDenied"):
                print(f"[bucket] {name} 사용 불가({code}) -> 다음 후보 시도")
                continue
            raise

    raise RuntimeError(
        "사용 가능한 버킷을 확보하지 못했습니다. 후보: " + ", ".join(candidates)
    )


def upload(s3, bucket: str) -> list[str]:
    """문서와 메타데이터를 업로드하고 업로드된 키 목록을 반환한다."""
    uploaded: list[str] = []

    for name in DESTINATIONS:
        doc_path = DOCS_DIR / f"{name}.txt"
        meta_path = META_DIR / f"{name}.metadata.json"

        if not doc_path.exists():
            raise FileNotFoundError(f"문서 없음: {doc_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"메타데이터 없음: {meta_path}")

        # 메타데이터가 Bedrock KB 스키마를 만족하는지 최소 검증
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        attrs = meta.get("metadataAttributes")
        if not isinstance(attrs, dict):
            raise ValueError(f"{meta_path}: metadataAttributes 누락")
        for required in ("category", "duration_hours"):
            if required not in attrs:
                raise ValueError(f"{meta_path}: '{required}' 속성 누락")

        doc_key = f"{PREFIX}{name}.txt"
        meta_key = f"{PREFIX}{name}.txt.metadata.json"

        s3.put_object(
            Bucket=bucket,
            Key=doc_key,
            Body=doc_path.read_bytes(),
            ContentType="text/plain; charset=utf-8",
        )
        uploaded.append(doc_key)

        s3.put_object(
            Bucket=bucket,
            Key=meta_key,
            Body=meta_path.read_bytes(),
            ContentType="application/json",
        )
        uploaded.append(meta_key)

        print(f"[upload] {name}: 문서 + 메타데이터 완료")

    return uploaded


def verify(s3, bucket: str) -> tuple[int, int]:
    """guides/ 아래 객체를 리스트해서 .txt / .metadata.json 개수를 센다."""
    paginator = s3.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])

    txt = [k for k in keys if k.endswith(".txt")]
    meta = [k for k in keys if k.endswith(".metadata.json")]

    print(f"\n[verify] s3://{bucket}/{PREFIX} 총 {len(keys)}개 객체")
    for k in sorted(keys):
        print(f"  - {k}")
    print(f"\n[verify] .txt = {len(txt)}개, .metadata.json = {len(meta)}개")

    return len(txt), len(meta)


def main() -> int:
    session = boto3.session.Session(region_name=REGION)
    s3 = session.client("s3")
    sts = session.client("sts")

    bucket = resolve_bucket(s3, sts)
    upload(s3, bucket)
    txt_count, meta_count = verify(s3, bucket)

    if txt_count == 6 and meta_count == 6:
        print(f"\n✅ 완료 기준 충족: .txt 6개 + .metadata.json 6개 = 12개")
        print(f"   버킷: {bucket}")
        print(f"   다음 단계에서 사용할 S3 URI: s3://{bucket}/{PREFIX}")
        return 0

    print(
        f"\n❌ 완료 기준 미충족 (.txt {txt_count}/6, .metadata.json {meta_count}/6)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
