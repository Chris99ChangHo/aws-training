"""강남 다이닝 컨시어지 예약 MCP 서버.

외부 예약 시스템을 대신하는 로컬 MCP 서버. FastMCP로 구현하며,
stdio 트랜스포트로 기동해 에이전트(MCP 클라이언트)와 통신한다.
"""

from __future__ import annotations

from datetime import datetime

from fastmcp import FastMCP

mcp = FastMCP(name="gangnam-dining-reservation")

# 식당별 좌석 현황. 실습용 정적 데이터이므로 예약 시스템 DB 대신 코드에
# 내장한다. 실제 예약 처리는 하지 않고 조회만 제공한다.
_TOTAL_SEATS_BY_RESTAURANT: dict[str, int] = {
    "강남 파스타 하우스": 20,
    "역삼 스시바": 10,
    "신사 분식당": 12,
    "강남 트라토리아": 16,
    "압구정 바베큐": 24,
    "르 비스트로": 14,
}

# (식당명, 날짜, 시간) 조합별로 이미 예약된 좌석 수. 없으면 0으로 취급한다.
_BOOKED_SEATS: dict[tuple[str, str, str], int] = {
    ("강남 파스타 하우스", "2026-07-29", "19:00"): 18,
    ("역삼 스시바", "2026-07-29", "19:00"): 10,
    ("강남 트라토리아", "2026-07-29", "20:00"): 6,
}


def _parse_date(date: str) -> None:
    """날짜 문자열이 YYYY-MM-DD 형식인지 검증한다.

    Raises:
        ValueError: 형식이 올바르지 않을 때.
    """
    datetime.strptime(date, "%Y-%m-%d")


def _parse_time(time: str) -> None:
    """시간 문자열이 HH:MM 형식인지 검증한다.

    Raises:
        ValueError: 형식이 올바르지 않을 때.
    """
    datetime.strptime(time, "%H:%M")


@mcp.tool
def check_availability(
    restaurant_name: str, date: str, time: str, party_size: int
) -> str:
    """식당의 예약 가능 여부와 남은 좌석 수를 조회한다.

    Args:
        restaurant_name: 예약 가능 여부를 조회할 식당 이름.
            예: "강남 파스타 하우스".
        date: 예약 날짜. "YYYY-MM-DD" 형식. 예: "2026-07-29".
        time: 예약 시간. "HH:MM" 형식(24시간제). 예: "19:00".
        party_size: 예약 인원 수. 1 이상의 정수.

    Returns:
        예약 가능 여부, 남은 좌석 수, 요청 인원 수용 가능 여부를 담은
        문자열. 식당을 찾지 못하거나 입력 형식이 올바르지 않으면 오류
        사유를 담은 문자열을 반환한다.
    """
    if party_size < 1:
        return "party_size는 1 이상이어야 합니다."

    try:
        _parse_date(date)
        _parse_time(time)
    except ValueError:
        return "날짜는 'YYYY-MM-DD', 시간은 'HH:MM' 형식으로 입력해 주세요."

    total_seats = _TOTAL_SEATS_BY_RESTAURANT.get(restaurant_name.strip())
    if total_seats is None:
        return f"'{restaurant_name}' 식당의 예약 정보를 찾지 못했습니다."

    booked = _BOOKED_SEATS.get((restaurant_name.strip(), date, time), 0)
    remaining_seats = total_seats - booked
    can_seat_party = remaining_seats >= party_size

    return (
        f"{restaurant_name} | {date} {time} | "
        f"남은 좌석: {remaining_seats}석 / 전체 {total_seats}석 | "
        f"{party_size}명 예약 가능: {'예' if can_seat_party else '아니오'}"
    )


if __name__ == "__main__":
    # 기본 트랜스포트는 stdio. 클라이언트(에이전트)가 이 스크립트를
    # 서브프로세스로 실행하고 표준 입출력으로 통신한다.
    mcp.run()
