"""코딩 에이전트 — 자연어 요청으로 코드를 작성하고 스스로 실행해 검증한다."""
from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from tools import read_file, run_shell, write_file

SYSTEM_PROMPT = """당신은 코드를 작성하는 에이전트입니다.

규칙:
1. workspace/ 안에서만 파일을 읽고·쓰고·실행합니다.
2. 파일을 작성한 뒤에는 반드시 run_shell로 실행해 결과를 확인합니다.
3. 실행이 실패하면 stderr에서 원인을 찾아 코드를 수정하고 다시 실행합니다.
4. 실행 성공이 확인될 때까지 완료를 선언하지 않습니다.
"""

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name="us-west-2")
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[run_shell, read_file, write_file],
)

if __name__ == "__main__":
    result = agent(
        "예약 인원이 식당 최대 수용 인원을 넘는지 검증하는 함수를 "
        "workspace/reservation.py에 만들어 주세요. "
        "한우명가 30명, 트라토리아 벨라 20명, 스시 오마카세 하루 8명 기준입니다"
    )
    print(str(result))
