# tools.py — 전문 에이전트들이 쓸 도구
import random

from strands import tool

RESTAURANTS = [
    {
        "name": "트라토리아 벨라",
        "cuisine": "이탈리안",
        "location": "강남역",
        "price_range": "3~6만원",
        "rating": 4.5,
        "menu": [
            {"item": "까르보나라", "price": 22000},
            {"item": "마르게리타 피자", "price": 25000},
        ],
    },
    {
        "name": "스시 오마카세 하루",
        "cuisine": "일식",
        "location": "강남역",
        "price_range": "6~9만원",
        "rating": 4.7,
        "menu": [
            {"item": "런치 오마카세", "price": 60000},
            {"item": "디너 오마카세", "price": 90000},
        ],
    },
    {
        "name": "한우명가",
        "cuisine": "한식",
        "location": "역삼역",
        "price_range": "4.5~7만원",
        "rating": 4.6,
        "menu": [
            {"item": "한우 등심", "price": 55000},
            {"item": "갈비탕", "price": 18000},
        ],
    },
    {
        "name": "르 비스트로",
        "cuisine": "프렌치",
        "location": "압구정역",
        "price_range": "5~8만원",
        "rating": 4.6,
        "menu": [
            {"item": "스테이크 프리츠", "price": 48000},
            {"item": "코스 메뉴", "price": 80000},
        ],
    },
    {
        "name": "매콤한 마라",
        "cuisine": "중식",
        "location": "강남역",
        "price_range": "2~3만원",
        "rating": 4.3,
        "menu": [
            {"item": "마라탕", "price": 12000},
            {"item": "마라샹궈", "price": 25000},
        ],
    },
]

_RESERVATIONS = {}  # (restaurant_name, date, time) -> {name, party_size}


def _avg_menu_price(restaurant: dict) -> int:
    prices = [m["price"] for m in restaurant["menu"]]
    return sum(prices) // len(prices)


@tool
def search_restaurants(location: str = "", cuisine: str = "", max_budget: int = 0) -> str:
    """조건(지역, 요리 종류, 1인 최대 예산)에 맞는 강남 일대 식당을 검색합니다.

    Args:
        location: 검색할 지역명(예: "강남역"). 비워두면 조건 없이 검색합니다.
        cuisine: 검색할 요리 종류(예: "중식"). 비워두면 조건 없이 검색합니다.
        max_budget: 1인 최대 예산(원). 0이면 예산 조건 없이 검색합니다.

    Returns:
        조건에 맞는 식당 목록을 JSON 문자열로 반환합니다.
    """
    results = []
    for r in RESTAURANTS:
        if location and location not in r["location"]:
            continue
        if cuisine and cuisine not in r["cuisine"]:
            continue
        if max_budget and _avg_menu_price(r) > max_budget:
            continue
        results.append(
            {
                "name": r["name"],
                "cuisine": r["cuisine"],
                "location": r["location"],
                "price_range": r["price_range"],
                "rating": r["rating"],
            }
        )
    import json

    return json.dumps(results, ensure_ascii=False)


@tool
def get_menu(restaurant_name: str) -> str:
    """식당 이름으로 대표 메뉴와 가격을 조회합니다.

    Args:
        restaurant_name: 조회할 식당의 정확한 이름.

    Returns:
        메뉴 목록을 JSON 문자열로 반환합니다. 식당을 찾지 못하면 빈 리스트.
    """
    import json

    for r in RESTAURANTS:
        if r["name"] == restaurant_name:
            return json.dumps(r["menu"], ensure_ascii=False)
    return json.dumps([], ensure_ascii=False)


@tool
def estimate_cost(restaurant_name: str, party_size: int) -> str:
    """식당의 인당 평균 메뉴 가격을 기준으로 총 예상 비용을 계산합니다.

    Args:
        restaurant_name: 비용을 추정할 식당의 정확한 이름.
        party_size: 예상 인원 수.

    Returns:
        총 예상 비용과 인당 비용을 담은 JSON 문자열.
    """
    import json

    for r in RESTAURANTS:
        if r["name"] == restaurant_name:
            per_person = _avg_menu_price(r)
            return json.dumps(
                {
                    "restaurant_name": restaurant_name,
                    "party_size": party_size,
                    "per_person": per_person,
                    "total": per_person * party_size,
                },
                ensure_ascii=False,
            )
    return json.dumps({"error": f"'{restaurant_name}'을 찾을 수 없습니다."}, ensure_ascii=False)


@tool
def check_reservations(restaurant_name: str, date: str, time: str, party_size: int) -> str:
    """식당의 예약 가능 여부와 남은 좌석을 확인합니다.

    Args:
        restaurant_name: 예약을 확인할 식당 이름.
        date: 예약 날짜(예: "2026-08-03" 또는 "내일").
        time: 예약 시간(예: "19:00" 또는 "저녁 7시").
        party_size: 예약 인원 수.

    Returns:
        예약 가능 여부와 남은 좌석 수를 담은 JSON 문자열.
    """
    import json

    seed = hash((restaurant_name, date, time)) % 1000
    rng = random.Random(seed)
    remaining_seats = rng.randint(0, 20)
    available = remaining_seats >= party_size

    return json.dumps(
        {
            "restaurant_name": restaurant_name,
            "date": date,
            "time": time,
            "party_size": party_size,
            "available": available,
            "remaining_seats": remaining_seats,
        },
        ensure_ascii=False,
    )


@tool
def create_reservation(
    restaurant_name: str, date: str, time: str, party_size: int, name: str
) -> str:
    """식당에 실제 예약을 생성합니다.

    Args:
        restaurant_name: 예약할 식당 이름.
        date: 예약 날짜.
        time: 예약 시간.
        party_size: 예약 인원 수.
        name: 예약자 이름.

    Returns:
        예약 생성 결과를 담은 JSON 문자열.
    """
    import json

    key = (restaurant_name, date, time)
    _RESERVATIONS[key] = {"name": name, "party_size": party_size}
    return json.dumps(
        {
            "status": "confirmed",
            "restaurant_name": restaurant_name,
            "date": date,
            "time": time,
            "party_size": party_size,
            "name": name,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    print(search_restaurants(location="강남역", cuisine="중식"))
    print(get_menu(restaurant_name="한우명가"))
    print(estimate_cost(restaurant_name="한우명가", party_size=4))
    print(check_reservations(restaurant_name="트라토리아 벨라", date="내일", time="저녁 7시", party_size=2))
    print(
        create_reservation(
            restaurant_name="트라토리아 벨라",
            date="내일",
            time="저녁 7시",
            party_size=2,
            name="홍길동",
        )
    )
