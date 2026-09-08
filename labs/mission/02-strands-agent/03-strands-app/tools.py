# tools.py — 강남 식당 도구
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


@tool
def search_restaurants(location: str = "", cuisine: str = "") -> str:
    """조건(지역, 요리 종류)에 맞는 강남 일대 식당을 검색합니다.

    Args:
        location: 검색할 지역명(예: "강남역"). 비워두면 지역 조건 없이 검색합니다.
        cuisine: 검색할 요리 종류(예: "이탈리안"). 비워두면 요리 종류 조건 없이 검색합니다.

    Returns:
        조건에 맞는 식당들의 이름/요리 종류/지역/가격대/평점을 정리한 문자열.
    """
    results = [
        r
        for r in RESTAURANTS
        if (not location or location in r["location"])
        and (not cuisine or cuisine in r["cuisine"])
    ]
    if not results:
        return "조건에 맞는 식당을 찾지 못했습니다."

    lines = []
    for r in results:
        lines.append(
            f"- {r['name']} ({r['cuisine']}, {r['location']}) "
            f"가격대 {r['price_range']}, 평점 {r['rating']}"
        )
    return "\n".join(lines)


@tool
def get_menu(restaurant_name: str) -> str:
    """식당 이름으로 대표 메뉴와 가격을 조회합니다.

    Args:
        restaurant_name: 조회할 식당의 정확한 이름(예: "트라토리아 벨라").

    Returns:
        대표 메뉴와 가격을 정리한 문자열. 식당을 찾지 못하면 안내 문자열.
    """
    for r in RESTAURANTS:
        if r["name"] == restaurant_name:
            lines = [f"{m['item']} — {m['price']:,}원" for m in r["menu"]]
            return f"{restaurant_name} 대표 메뉴:\n" + "\n".join(lines)
    return f"'{restaurant_name}'을 찾을 수 없습니다."


if __name__ == "__main__":
    print(search_restaurants(location="강남역", cuisine="이탈리안"))
    print()
    print(get_menu(restaurant_name="한우명가"))
