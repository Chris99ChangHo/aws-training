# mcp_server.py — 예약 MCP 서버
import random

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("reservation-server")


@mcp.tool()
def check_reservations(restaurant_name: str, date: str, time: str, party_size: int) -> str:
    """식당의 예약 가능 여부와 남은 좌석을 확인합니다.

    Args:
        restaurant_name: 예약을 확인할 식당 이름.
        date: 예약 날짜(예: "2026-08-03" 또는 "내일").
        time: 예약 시간(예: "19:00" 또는 "저녁 7시").
        party_size: 예약 인원 수.

    Returns:
        예약 가능 여부와 남은 좌석 수를 담은 문자열.
    """
    # 데모용: 시드를 식당명+날짜+시간으로 고정해 항상 같은 결과가 나오게 함
    seed = hash((restaurant_name, date, time)) % 1000
    rng = random.Random(seed)
    remaining_seats = rng.randint(0, 20)
    available = remaining_seats >= party_size

    status = "예약 가능" if available else "예약 불가"
    return (
        f"{restaurant_name} / {date} {time} / 요청 인원 {party_size}명\n"
        f"상태: {status} (남은 좌석: {remaining_seats}석)"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
