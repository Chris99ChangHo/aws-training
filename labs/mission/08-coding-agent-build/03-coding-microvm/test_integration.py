"""Coder와 Tester(MicroVM)를 조율하는 통합 테스트."""
from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from tester_microvm import tester_agent

CODER_SYSTEM_PROMPT = """당신은 Coder 에이전트입니다.
요청에 맞는 Python 함수를 작성합니다.
경계값과 에러 처리를 빠짐없이 포함하세요."""

coder_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name="us-west-2",
)
coder_agent = Agent(
    model=coder_model,
    system_prompt=CODER_SYSTEM_PROMPT,
    tools=[],
)


def run_integration_test() -> str:
    """코디네이터가 Coder와 Tester를 조율하는 통합 테스트."""
    request = "예약 인원 검증 함수를 작성해 주세요. 최소 1명, 최대 20명입니다."

    coder_response = str(coder_agent(request))
    print(f"[Coder] 응답 수신 ({len(coder_response)} chars)")

    test_request = (
        f"다음 코드를 테스트해 주세요:\n\n{coder_response}\n\n"
        "파일명은 reservation.py입니다. "
        "경계값(0, 1, 20, 21)과 비정상 입력(음수, None)을 테스트하세요."
    )
    tester_response = str(tester_agent(test_request))
    print(f"[Tester] 결과: {tester_response}")

    return tester_response


if __name__ == "__main__":
    result = run_integration_test()
    print(f"\n최종 결과: {result}")
