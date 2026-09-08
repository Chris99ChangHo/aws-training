# 01_upload_data.py — 식당 데이터 + 메타데이터를 S3에 업로드
import zipfile
from pathlib import Path
import boto3

REGION = "us-west-2"
s3 = boto3.client("s3", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)

account_id = sts.get_caller_identity()["Account"]
bucket = f"dining-kb-data-{account_id}"

try:
    s3.create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": REGION},
    )
    print(f"버킷 생성: {bucket}")
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f"기존 버킷 사용: {bucket}")

# 압축 해제
data_dir = Path("rag-lab-data")
with zipfile.ZipFile("rag-lab-data-ko.zip") as z:
    z.extractall(data_dir)

count = 0
for f in sorted(data_dir.rglob("*")):
    if f.suffix.lower() in (".docx", ".json", ".xlsx"):
        key = f"restaurant-docs/{f.name}"
        s3.upload_file(str(f), bucket, key)
        count += 1
        print(f"업로드: {key}")

print(f"\n총 {count}개 객체 업로드 완료")