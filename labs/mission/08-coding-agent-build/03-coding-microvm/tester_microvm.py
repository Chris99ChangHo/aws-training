"""Tester 에이전트 — MicroVM 샌드박스 안에서 pytest를 실행한다."""
from __future__ import annotations

import re

from strands import Agent, tool
from strands.models import BedrockModel

from sandbox_runner import (
    create_sandbox,
    destroy_sandbox,
    get_auth_token,
    run_tests_in_microvm,
)


@tool
def run_tests_in_sandbox(
    test_code: str,
    source_code: str,
    source_filename: str,
) -> str:
    """MicroVM 샌드박스 안에서 pytest를 실행합니다."""
    microvm_id, endpoint = create_sandbox()
    try:
        auth_token = get_auth_token(microvm_id)
        result = run_tests_in_microvm(
            endpoint=endpoint,
            auth_token=auth_token,
            source_code=source_code,
            source_filename=source_filename,
            test_code=test_code,
        )
        return parse_pytest_output(result["output"])
    finally:
        destroy_sandbox(microvm_id)


def parse_pytest_output(output: str) -> str:
    """pytest 출력에서 passed/failed 수를 추출한다."""
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)

    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0

    summary = f"passed={passed} failed={failed}"

    if failed > 0:
        return f"{summary}\n\n--- 실패 상세 ---\n{output}"
    return summary


TESTER_SYSTEM_PROMPT = """당신은 Tester 에이전트입니다.
주어진 소스 코드에 대해 테스트를 작성하고 MicroVM 샌드박스에서 실행합니다.
경계값, 오류 케이스, 정상 케이스를 모두 커버하세요.
결과는 마지막 줄에 passed=N failed=M 형식으로 보고합니다."""

tester_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-6",
    region_name="us-west-2",
)

tester_agent = Agent(
    model=tester_model,
    system_prompt=TESTER_SYSTEM_PROMPT,
    tools=[run_tests_in_sandbox],
)
