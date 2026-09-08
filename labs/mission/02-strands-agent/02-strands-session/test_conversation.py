# test_conversation.py — 멀티턴 + 재시작 복원 테스트
#
# 1부: session_id "dining-session-001"에서 5턴 대화를 이어갑니다.
# 2부: 프로세스를 종료했다가(별도 실행) 같은 session_id로 재기동해
#      이전 대화에서 추천한 식당을 회상하는지 확인합니다.
#
# 사용법:
#   python test_conversation.py part1   # 5턴 대화 진행
#   python test_conversation.py part2   # "재시작" 후 회상 테스트
import sys

from agent import build_agent, reservation_mcp

TURNS_PART1 = [
    "강남역 근처 데이트하기 좋은 식당 추천해 주세요",
    "그중에서 1인 5만원 이하는?",
    "매운 건 못 먹으니 매콤한 마라는 빼 주세요",
    "그럼 남은 곳 중에 평점이 가장 높은 곳은 어디인가요?",
    "거기 대표 메뉴도 알려 주세요",
]

TURN_PART2 = "지난번 추천받은 그 식당, 내일 저녁 7시에 2명 예약 가능한지 확인해 주세요"


def run_part1():
    with reservation_mcp:
        agent = build_agent()
        for i, turn in enumerate(TURNS_PART1, 1):
            print(f"\n=== 턴 {i}: {turn} ===")
            response = agent(turn)
            print(response)


def run_part2():
    # 새 프로세스에서 같은 session_id로 에이전트를 다시 만들면
    # FileSessionManager가 ./sessions에서 이전 대화를 복원합니다.
    with reservation_mcp:
        agent = build_agent()
        print(f"\n=== 재시작 후 질문: {TURN_PART2} ===")
        response = agent(TURN_PART2)
        print(response)


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "part1"
    if part == "part1":
        run_part1()
    elif part == "part2":
        run_part2()
    else:
        print("사용법: python test_conversation.py [part1|part2]")
