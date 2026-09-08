# create_memory.py — 콘솔 대안
from bedrock_agentcore.memory import MemoryClient

client = MemoryClient(region_name="us-west-2")

# 💡: create_memory_and_wait — 생성 후 ACTIVE가 될 때까지 폴링
#     생성 직후 CREATING 상태에서는 이벤트 저장이 실패하므로 대기가 필요합니다
memory = client.create_memory_and_wait(
    name="dining_memory",
    strategies=[{"semanticMemoryStrategy": {"name": "dining_facts"}}],
    event_expiry_days=30,
)
print(f"✅ Memory 생성 완료 (ACTIVE): {memory['id']}")