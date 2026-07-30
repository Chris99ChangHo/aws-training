"""강남 다이닝 리뷰 MCP 서버.

손님들이 남긴 식당 리뷰를 조회하는 로컬 MCP 서버. FastMCP로 구현하며,
stdio 트랜스포트로 기동해 에이전트(MCP 클라이언트)와 통신한다.
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("restaurant-reviews")

# 강남 일대 식당 5곳의 평점·리뷰. 실습용 정적 데이터이므로 리뷰 DB
# 대신 코드에 내장한다. 식당 이름 -> {rating, reviews} 딕셔너리.
_RESTAURANT_REVIEWS: dict[str, dict] = {
    "트라토리아 벨라": {
        "rating": 4.5,
        "reviews": [
            "파스타 면발이 정말 완벽했어요. 분위기도 좋아서 데이트 코스로 추천합니다.",
            "웨이팅이 좀 길었지만 음식 맛은 그만큼 값어치가 있었어요.",
            "화이트 와인이랑 리조또 조합이 최고였습니다.",
        ],
    },
    "스시 오마카세 하루": {
        "rating": 4.8,
        "reviews": [
            "셰프님이 직접 설명해주시는 오마카세 코스가 인상적이었어요.",
            "재료 신선도가 확실히 다릅니다. 가격대는 있지만 만족스러웠어요.",
        ],
    },
    "한우명가": {
        "rating": 4.3,
        "reviews": [
            "한우 마블링이 예술이에요. 회식 장소로 인기 많은 이유를 알겠네요.",
            "가격이 좀 있지만 특별한 날 방문하기 좋습니다.",
            "고기 굽는 서비스가 친절했어요.",
        ],
    },
    "르 비스트로": {
        "rating": 4.6,
        "reviews": [
            "코코뱅이 진짜 프랑스 가정식 같았어요. 분위기도 아늑합니다.",
            "와인 리스트가 다양해서 페어링하기 좋았어요.",
        ],
    },
    "매콤한 마라": {
        "rating": 4.1,
        "reviews": [
            "마라탕 맵기 조절이 잘 되어 있어서 매운맛 초보도 즐길 수 있어요.",
            "양이 많아서 배부르게 먹었습니다. 재방문 의사 있어요.",
            "향신료 향이 강한 편이니 처음이면 순한맛부터 추천합니다.",
        ],
    },
}


@mcp.tool()
def restaurant_reviews(restaurant_name: str) -> str:
    """식당의 평점과 최근 리뷰를 조회한다.

    Args:
        restaurant_name: 리뷰를 조회할 식당 이름. 예: "트라토리아 벨라",
            "스시 오마카세 하루", "한우명가", "르 비스트로", "매콤한 마라".
            공백을 제거하고 부분 일치로 비교하므로 정확한 전체 이름이
            아니어도 된다.

    Returns:
        평점과 리뷰 목록을 담은 문자열. 등록된 식당이 아니면 안내
        문구를 반환한다.
    """
    query = restaurant_name.strip()
    matched_name = next(
        (name for name in _RESTAURANT_REVIEWS if query in name), None
    )

    if matched_name is None:
        return f"'{restaurant_name}' 식당의 리뷰 정보를 찾지 못했습니다."

    data = _RESTAURANT_REVIEWS[matched_name]
    reviews_text = "\n".join(f"- {review}" for review in data["reviews"])
    return f"[{matched_name}] 평점: {data['rating']} / 5.0\n{reviews_text}"


if __name__ == "__main__":
    # 기본 트랜스포트는 stdio. 클라이언트(에이전트)가 이 스크립트를
    # 서브프로세스로 실행하고 표준 입출력으로 통신한다.
    mcp.run()
