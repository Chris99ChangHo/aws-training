"""DynamoDB 예약 내역 조회 클라이언트."""
from __future__ import annotations

import boto3
from boto3.dynamodb.conditions import Key

REGION = "us-west-2"
TABLE_NAME = "dining-reservations"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def get_reservations(actor_id: str, limit: int = 10) -> list[dict]:
    """actor_id의 최근 예약 내역을 반환한다."""
    resp = table.query(
        KeyConditionExpression=Key("actor_id").eq(actor_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return resp.get("Items", [])


def create_reservation(
    actor_id: str,
    restaurant: str,
    date: str,
    time: str,
    party_size: int,
) -> dict:
    """예약을 생성하고 저장된 아이템을 반환한다."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "actor_id": actor_id,
        "reserved_at": now,
        "restaurant": restaurant,
        "date": date,
        "time": time,
        "party_size": party_size,
        "status": "confirmed",
    }
    table.put_item(Item=item)
    return item


if __name__ == "__main__":
    items = get_reservations("user-001")
    print(f"예약 {len(items)}건:")
    for item in items:
        print(f"  {item['restaurant']} — {item['date']} {item['time']} ({item['party_size']}명)")
