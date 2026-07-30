"""강남 다이닝 컨시어지 도구 모음.

Strands Agents SDK의 ``@tool`` 데코레이터로 식당 검색과 메뉴 조회 도구를
정의한다. 식당 데이터는 실습 목적상 코드에 내장한 정적 목록을 쓴다.
"""

from __future__ import annotations

from strands import tool

# 강남 일대 식당 6곳. 실습용 정적 데이터이므로 DB 대신 코드에 내장한다.
# RESTAURANTS는 Streamlit 앱의 카드 렌더링에서도 재사용하므로 공개
# 이름(밑줄 없음)으로 노출한다.
RESTAURANTS: list[dict] = [
    {
        "name": "gangnam_pasta_house",
        "display_name": "강남 파스타 하우스",
        "area": "강남역",
        "cuisine": "이탈리안",
        "price_range": "중가",
        "rating": 4.5,
        "accepts_reservation": True,
        "menu": {
            "트러플 크림 파스타": 24000,
            "봉골레 파스타": 19000,
            "마르게리타 피자": 21000,
            "티라미수": 9000,
        },
    },
    {
        "name": "yeoksam_sushi_bar",
        "display_name": "역삼 스시바",
        "area": "역삼역",
        "cuisine": "일식",
        "price_range": "고가",
        "rating": 4.8,
        "accepts_reservation": True,
        "menu": {
            "오마카세 코스": 89000,
            "연어 사케동": 18000,
            "모둠초밥": 32000,
            "미소국": 4000,
        },
    },
    {
        "name": "sinsa_bunsik",
        "display_name": "신사 분식당",
        "area": "신사역",
        "cuisine": "한식",
        "price_range": "저가",
        "rating": 4.1,
        "accepts_reservation": False,
        "menu": {
            "떡볶이": 6000,
            "김밥": 4000,
            "라면": 5000,
            "순대": 6000,
        },
    },
    {
        "name": "gangnam_trattoria",
        "display_name": "강남 트라토리아",
        "area": "강남역",
        "cuisine": "이탈리안",
        "price_range": "고가",
        "rating": 4.6,
        "accepts_reservation": True,
        "menu": {
            "안심 스테이크": 45000,
            "리조또": 26000,
            "카프레제 샐러드": 15000,
            "판나코타": 10000,
        },
    },
    {
        "name": "apgujeong_bbq",
        "display_name": "압구정 바베큐",
        "area": "압구정역",
        "cuisine": "한식",
        "price_range": "고가",
        "rating": 4.7,
        "accepts_reservation": True,
        "menu": {
            "한우 갈비살": 42000,
            "삼겹살": 18000,
            "된장찌개": 9000,
            "냉면": 11000,
        },
    },
    {
        "name": "le_bistro",
        "display_name": "르 비스트로",
        "area": "강남역",
        "cuisine": "프렌치",
        "price_range": "고가",
        "rating": 4.4,
        "accepts_reservation": True,
        "menu": {
            "onion 스프": 12000,
            "코코뱅": 32000,
            "안심 스테이크 프리츠": 38000,
            "크렘 브륄레": 11000,
        },
    },
]


@tool
def search_restaurants(area: str | None = None, cuisine: str | None = None) -> str:
    """조건에 맞는 강남 일대 식당을 검색한다.

    지역(area)과 음식 종류(cuisine) 조건으로 식당 목록을 필터링한다.
    두 조건은 모두 선택이며, 지정하지 않은 조건은 무시된다. 대소문자와
    공백에 관계없이 부분 일치로 비교한다.

    Args:
        area: 찾고 싶은 지역명. 예: "강남역", "역삼역", "신사역", "압구정역".
            지정하지 않으면 지역으로 필터링하지 않는다.
        cuisine: 찾고 싶은 음식 종류. 예: "이탈리안", "일식", "한식", "프렌치".
            지정하지 않으면 음식 종류로 필터링하지 않는다.

    Returns:
        조건에 맞는 식당들의 이름, 지역, 음식 종류, 가격대, 예약 가능 여부를
        줄 단위로 나열한 문자열. 조건에 맞는 식당이 없으면 안내 문구를
        반환한다.
    """
    matches = [
        restaurant
        for restaurant in RESTAURANTS
        if (area is None or area.strip() in restaurant["area"])
        and (cuisine is None or cuisine.strip() in restaurant["cuisine"])
    ]

    if not matches:
        return "조건에 맞는 식당을 찾지 못했습니다."

    lines = [
        f"{restaurant['display_name']} | {restaurant['area']} | "
        f"{restaurant['cuisine']} | 가격대: {restaurant['price_range']} | "
        f"예약 가능: {'예' if restaurant['accepts_reservation'] else '아니오'}"
        for restaurant in matches
    ]
    return "\n".join(lines)


@tool
def get_menu(restaurant_name: str) -> str:
    """지정한 식당의 메뉴와 가격을 조회한다.

    Args:
        restaurant_name: 메뉴를 조회할 식당의 이름. `search_restaurants`가
            반환한 식당명(예: "강남 파스타 하우스")을 그대로 전달하면 된다.
            공백을 제거하고 부분 일치로 비교하므로 정확한 전체 이름이
            아니어도 된다.

    Returns:
        메뉴명과 가격(원)을 줄 단위로 나열한 문자열. 식당을 찾지 못하면
        안내 문구를 반환한다.
    """
    query = restaurant_name.strip()
    restaurant = next(
        (r for r in RESTAURANTS if query in r["display_name"] or query in r["name"]),
        None,
    )

    if restaurant is None:
        return f"'{restaurant_name}' 식당을 찾지 못했습니다."

    lines = [
        f"{item}: {price:,}원" for item, price in restaurant["menu"].items()
    ]
    return f"[{restaurant['display_name']} 메뉴]\n" + "\n".join(lines)
