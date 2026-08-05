"""MCP 서버 — FastMCP로 식당 검색 도구를 제공합니다."""
from mcp.server.fastmcp import FastMCP
from typing import Optional

# MCP 서버 인스턴스 생성
mcp = FastMCP("restaurant-service")

# 식당 데이터
RESTAURANTS = [
    {"name": "트라토리아 벨라", "cuisine": "이탈리안", "location": "강남역", "price": 50000, "rating": 4.5},
    {"name": "한우명가", "cuisine": "한식", "location": "역삼역", "price": 80000, "rating": 4.7},
    {"name": "매콤한 마라", "cuisine": "중식", "location": "강남역", "price": 25000, "rating": 4.1},
    {"name": "르 비스트로", "cuisine": "프렌치", "location": "압구정", "price": 100000, "rating": 4.6},
    {"name": "스시 오마카세 하루", "cuisine": "일식", "location": "강남역", "price": 100000, "rating": 4.8},
]

@mcp.tool()
def search_restaurants(
    location: Optional[str] = None,
    cuisine: Optional[str] = None,
    max_price: Optional[int] = None,
) -> str:
    """조건에 맞는 식당을 검색합니다.

    Args:
        location: 위치 (강남역, 역삼역, 압구정)
        cuisine: 음식 종류 (이탈리안, 한식, 중식, 프렌치, 일식)
        max_price: 1인 최대 예산 (원)
    """
    results = []
    for r in RESTAURANTS:
        if location and location not in r["location"]:
            continue
        if cuisine and cuisine not in r["cuisine"]:
            continue
        if max_price and r["price"] > max_price:
            continue
        results.append(r)

    if not results:
        return "조건에 맞는 식당이 없습니다. 조건을 완화해보세요."

    lines = []
    for r in results:
        lines.append(f"🍽️ {r['name']} ({r['cuisine']}) — {r['location']}, {r['price']:,}원/인, 평점 {r['rating']}")
    return "\n".join(lines)

@mcp.tool()
def get_restaurant_details(name: str) -> str:
    """식당 상세 정보를 조회합니다.

    Args:
        name: 식당 이름
    """
    for r in RESTAURANTS:
        if r["name"] == name:
            return (
                f"식당: {r['name']}\n"
                f"종류: {r['cuisine']}\n"
                f"위치: {r['location']}\n"
                f"가격: {r['price']:,}원/인\n"
                f"평점: {r['rating']}/5.0"
            )
    return f"'{name}' 식당을 찾을 수 없습니다."

if __name__ == "__main__":
    import sys

    # --transport streamable-http 플래그가 있으면 HTTP 서버 모드로 실행 (Part 3에서 사용)
    if "streamable-http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()  # 기본 stdio 모드