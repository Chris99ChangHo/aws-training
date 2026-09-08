"""DynamoDB 예약 테이블 생성 스크립트."""
from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

REGION = "us-west-2"
TABLE_NAME = "dining-reservations"


def main() -> int:
    dynamodb = boto3.client("dynamodb", region_name=REGION)

    try:
        dynamodb.describe_table(TableName=TABLE_NAME)
        print(f"테이블 이미 존재: {TABLE_NAME}")
        return 0
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "actor_id", "KeyType": "HASH"},
            {"AttributeName": "reserved_at", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "actor_id", "AttributeType": "S"},
            {"AttributeName": "reserved_at", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"테이블 생성 시작: {TABLE_NAME}")

    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=TABLE_NAME)
    print(f"테이블 ACTIVE: {TABLE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
