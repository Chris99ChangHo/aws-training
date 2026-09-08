# test_memory.py — 세션 간 취향 기억 검증 (2세션 시나리오)
import time
from dining_agent_memory import create_agent

# --- 세션 1: 취향 입력 ---
print("=== 세션 1 (session-dining-001): 취향 입력 ===")
agent1 = create_agent(session_id="session-dining-001")
print(agent1("이탈리안 좋아해요, 매운 음식 못 먹어요"))

print("\n장기 기억 추출 대기 중 (90초)...")
time.sleep(90)

# --- 세션 2: 새 session_id, 같은 actor_id ---
print("=== 세션 2 (session-dining-002): 추천만 요청 ===")
agent2 = create_agent(session_id="session-dining-002")
print(agent2("강남 식당 추천해 주세요"))