"""
09_upload_new_and_verify_autosync.py

새로 추가한 관광지 문서를 S3에 업로드하고, S3 이벤트로 Lambda가
자동으로 ingestion job을 시작하는지 검증한다.

검증 흐름:
  1. 업로드 직전의 최근 ingestion job ID를 기록
  2. 신규 문서 + 메타데이터 업로드
  3. 새로운 ingestion job이 자동 생성되는지 폴링 (Lambda 동작 확인)
  4. 해당 job이 COMPLETE 될 때까지 대기
  5. 새 관광지가 검색되는지 확인

사용법:
    python 09_upload_new_and_verify_autosync.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import boto3

REGION = "us-east-1"
PREFIX = "guides/"
DATA_ROOT = Path(__file__).parent / "travel-kb-ko"

# 이번에 새로 추가하는 관광지
NEW_DESTINATIONS = ["창덕궁", "국립중앙박물관", "서울숲"]


def log(msg: str) -> None:
    print(msg, flush=True)


def recent_job_ids(agent, kb_id: str, ds_id: str) -> set[str]:
    resp = agent.list_ingestion_jobs(
        knowledgeBaseId=kb_id, dataSourceId=ds_id, maxResults=50
    )
    return {j["ingestionJobId"] for j in resp.get("ingestionJobSummaries", [])}


def upload(s3, bucket: str) -> None:
    for name in NEW_DESTINATIONS:
        doc = DATA_ROOT / "destinations" / f"{name}.txt"
        meta = DATA_ROOT / "metadata" / f"{name}.metadata.json"
        if not doc.exists() or not meta.exists():
            raise FileNotFoundError(f"{name}: 문서 또는 메타데이터 없음")

        s3.put_object(
            Bucket=bucket,
            Key=f"{PREFIX}{name}.txt",
            Body=doc.read_bytes(),
            ContentType="text/plain; charset=utf-8",
        )
        s3.put_object(
            Bucket=bucket,
            Key=f"{PREFIX}{name}.txt.metadata.json",
            Body=meta.read_bytes(),
            ContentType="application/json",
        )
        log(f"[upload] {name} 업로드 완료")


def wait_for_new_job(agent, kb_id: str, ds_id: str, before: set[str]) -> str:
    """Lambda가 자동으로 시작한 새 job을 찾는다."""
    log("[autosync] Lambda가 시작한 새 ingestion job 대기 중...")
    deadline = time.time() + 180
    while time.time() < deadline:
        now = recent_job_ids(agent, kb_id, ds_id)
        new = now - before
        if new:
            job_id = new.pop()
            log(f"[autosync] ✅ 자동 생성된 job 발견: {job_id}")
            return job_id
        time.sleep(5)
    raise TimeoutError(
        "새 ingestion job이 자동 생성되지 않았습니다 (Lambda 트리거 실패)"
    )


def wait_complete(agent, kb_id: str, ds_id: str, job_id: str) -> dict:
    deadline = time.time() + 900
    while time.time() < deadline:
        job = agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        status = job["status"]
        if status == "COMPLETE":
            log("[autosync] 동기화 COMPLETE")
            return job
        if status == "FAILED":
            raise RuntimeError(f"동기화 실패: {job.get('failureReasons')}")
        log(f"[autosync] 상태: {status} ... 대기")
        time.sleep(10)
    raise TimeoutError("동기화가 완료되지 않았습니다")


def verify_search(kb_id: str) -> bool:
    """새 관광지가 실제로 검색되는지 확인한다."""
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    all_ok = True

    queries = {
        "창덕궁": "창덕궁 후원과 인정전",
        "국립중앙박물관": "국립중앙박물관 사유의 방 반가사유상",
        "서울숲": "서울숲 생태공원 성수동",
    }

    log("\n[verify] 신규 관광지 검색 확인")
    for expected, query in queries.items():
        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
        )
        names = [
            r["location"]["s3Location"]["uri"].rsplit("/", 1)[-1].replace(".txt", "")
            for r in resp["retrievalResults"]
        ]
        hit = expected in names
        all_ok = all_ok and hit
        mark = "✅" if hit else "❌"
        log(f"  {mark} {query!r}")
        log(f"      상위3={names}")

    return all_ok


def main() -> int:
    kb_info_path = Path(__file__).parent / "kb_info.json"
    with open(kb_info_path, encoding="utf-8") as fh:
        info = json.load(fh)
    kb_id, ds_id, bucket = info["knowledgeBaseId"], info["dataSourceId"], info["bucket"]

    session = boto3.session.Session(region_name=REGION)
    s3 = session.client("s3")
    agent = session.client("bedrock-agent")

    before = recent_job_ids(agent, kb_id, ds_id)
    log(f"[info] 업로드 전 기존 job 수: {len(before)}")

    upload(s3, bucket)

    job_id = wait_for_new_job(agent, kb_id, ds_id, before)
    job = wait_complete(agent, kb_id, ds_id, job_id)

    stats = job.get("statistics", {})
    log(f"\n[stats] 스캔={stats.get('numberOfDocumentsScanned')} "
        f"신규={stats.get('numberOfNewDocumentsIndexed')} "
        f"수정={stats.get('numberOfModifiedDocumentsIndexed')} "
        f"실패={stats.get('numberOfDocumentsFailed')}")

    # 객체 수 확인
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=PREFIX):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    txt = [k for k in keys if k.endswith(".txt")]
    meta = [k for k in keys if k.endswith(".metadata.json")]
    log(f"[s3] guides/ 총 {len(keys)}개 (.txt {len(txt)}, .metadata.json {len(meta)})")

    # 인덱싱 완료 후 벡터 검색에 반영되기까지 약간의 지연이 있다.
    log("\n[verify] 인덱스 반영 대기(45초)...")
    time.sleep(45)

    ok = verify_search(kb_id)

    log("\n" + "=" * 60)
    if ok:
        log("✅ 자동 동기화 검증 성공")
        log("   S3 업로드 -> S3 이벤트 -> Lambda -> ingestion job -> 검색 반영")
        log("=" * 60)
        return 0

    log("❌ 신규 관광지 일부가 검색되지 않았습니다")
    log("=" * 60)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
