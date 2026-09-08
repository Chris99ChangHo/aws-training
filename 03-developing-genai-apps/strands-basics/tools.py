"""커스텀 도구 — 식당 검색 및 예약 도구를 정의합니다."""
from strands import tool
from typing import Optional
import uuid
from datetime import datetime

# 로컬 식당 데이터 (DynamoDB 대신 Python dict 사용)
RESTAURANTS = {
    "rest-001": {
        "id": "rest-001",
        "name": "트라토리아 벨라",
        "cuisine": "이탈리안",
        "location": "강남역",
        "price_min": 40000,
        "price_max": 60000,
        "rating": 4.5,
        "features": ["데이트", "와인 리스트", "프라이빗 룸"],
        "menu": "수제 파스타, 화덕 피자",
        "hours": "11:30-22:00",
        "closed": "월요일",
    },
    "rest-002": {
        "id": "rest-002",
        "name": "스시 오마카세 하루",
        "cuisine": "일식",
        "location": "강남역",
        "price_min": 80000,
        "price_max": 150000,
        "rating": 4.8,
        "features": ["오마카세", "카운터석", "기념일"],
        "menu": "오마카세 코스, 사케 페어링",
        "hours": "17:00-22:00",
        "closed": "일요일",
    },
    "rest-003": {
        "id": "rest-003",
        "name": "한우명가",
        "cuisine": "한식",
        "location": "역삼역",
        "price_min": 50000,
        "price_max": 80000,
        "rating": 4.3,
        "features": ["단체", "프라이빗 룸", "주차"],
        "menu": "한우 구이, 된장찌개",
        "hours": "11:00-22:00",
        "closed": "연중무휴",
    },
    "rest-004": {
        "id": "rest-004",
        "name": "르 비스트로",
        "cuisine": "프렌치",
        "location": "압구정",
        "price_min": 70000,
        "price_max": 120000,
        "rating": 4.6,
        "features": ["데이트", "기념일", "와인 셀러"],
        "menu": "프렌치 코스, 와인 페어링",
        "hours": "12:00-22:00",
        "closed": "월요일",
    },
    "rest-005": {
        "id": "rest-005",
        "name": "매콤한 마라",
        "cuisine": "중식",
        "location": "강남역",
        "price_min": 20000,
        "price_max": 30000,
        "rating": 4.1,
        "features": ["단체", "가성비", "매운맛"],
        "menu": "마라탕, 마라샹궈, 꿔바로우",
        "hours": "11:00-23:00",
        "closed": "연중무휴",
    },
}

# 예약 저장소 (로컬 리스트)
reservations = []

@tool
def search_restaurants(
    cuisine: Optional[str] = None,
    location: Optional[str] = None,
    budget_per_person: Optional[int] = None,
    features: Optional[str] = None,
) -> str:
    """조건에 맞는 식당을 검색합니다.

    Args:
        cuisine: 음식 카테고리 (예: 이탈리안, 일식, 한식, 프렌치, 중식)
        location: 위치 (예: 강남역, 역삼역, 압구정)
        budget_per_person: 1인 예산 (원 단위, 예: 50000)
        features: 원하는 특징 (예: 데이트, 단체, 기념일, 가성비)

    Returns:
        검색 결과를 포맷팅한 문자열
    """
    results = []

    for rest in RESTAURANTS.values():
        # 카테고리 필터
        if cuisine and cuisine not in rest["cuisine"]:
            continue
        # 위치 필터
        if location and location not in rest["location"]:
            continue
        # 예산 필터 — 최소 가격이 예산 이하인 식당
        if budget_per_person and rest["price_min"] > budget_per_person:
            continue
        # 특징 필터
        if features:
            feature_list = [f.strip() for f in features.split(",")]
            if not any(f in rest["features"] for f in feature_list):
                continue
        results.append(rest)

    if not results:
        return "조건에 맞는 식당을 찾지 못했습니다. 조건을 변경해보세요."

    formatted = []
    for r in results:
        price_range = f"{r['price_min']//10000}~{r['price_max']//10000}만원"
        formatted.append(
            f"🍽️ {r['name']} (ID: {r['id']})\n"
            f"   카테고리: {r['cuisine']} | 위치: {r['location']}\n"
            f"   가격: 1인 {price_range} | 평점: {r['rating']}\n"
            f"   특징: {', '.join(r['features'])}\n"
            f"   대표 메뉴: {r['menu']}\n"
            f"   영업시간: {r['hours']} | 휴무: {r['closed']}"
        )

    return f"총 {len(results)}개 식당을 찾았습니다.\n\n" + "\n\n".join(formatted)

@tool
def create_reservation(
    restaurant_id: str,
    date: str,
    time: str,
    party_size: int,
    customer_name: str,
) -> str:
    """식당 예약을 생성합니다.

    Args:
        restaurant_id: 식당 ID (예: rest-001)
        date: 예약 날짜 (예: 2026-07-31)
        time: 예약 시간 (예: 19:00)
        party_size: 인원 수
        customer_name: 예약자 이름

    Returns:
        예약 확인 메시지
    """
    # 식당 존재 여부 확인
    if restaurant_id not in RESTAURANTS:
        return f"식당 ID '{restaurant_id}'를 찾을 수 없습니다."

    restaurant = RESTAURANTS[restaurant_id]

    # 예약 생성
    reservation = {
        "reservation_id": str(uuid.uuid4())[:8],
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant["name"],
        "date": date,
        "time": time,
        "party_size": party_size,
        "customer_name": customer_name,
        "created_at": datetime.now().isoformat(),
    }

    reservations.append(reservation)

    return (
        f"✅ 예약이 완료되었습니다!\n\n"
        f"예약 번호: {reservation['reservation_id']}\n"
        f"식당: {restaurant['name']}\n"
        f"날짜: {date}\n"
        f"시간: {time}\n"
        f"인원: {party_size}명\n"
        f"예약자: {customer_name}"
    )