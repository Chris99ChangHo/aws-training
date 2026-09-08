"""Tester 에이전트 — 테스트를 작성·실행만 한다 (read_file 없음, 소스는 인자로 받음).

역할별로 도구를 다르게 준다: Coder만 파일을 쓰고, Reviewer는 읽기만,
Tester는 테스트 파일 작성과 실행만 한다.
"""
from __future__ import annotations

from strands import Agent, tool
from strands.models import BedrockModel

from tools import run_shell, write_file

TESTER_SYSTEM_PROMPT = """당신은 테스트 엔지니어입니다. 검증 대상 함수의 테스트를 작성해
test_reservation.py에 저장하고 실행합니다.
경계값, 잘못된 입력, 정상 케이스를 모두 포함하세요.
pytest 실행이 끝나면 결과를 요약 표나 부연 설명 없이 정확히
"passed=N failed=M" 한 줄로만 보고하세요 (N·M은 실제 숫자). 이 줄이
당신의 응답에서 가장 마지막 내용이어야 합니다.
실패한 테스트가 있으면 이 줄 앞에 실패 로그(stderr 포함)를 붙이세요."""

tester = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name="us-west-2"),
    system_prompt=TESTER_SYSTEM_PROMPT,
    tools=[write_file, run_shell],
)


@tool
def run_tests(path: str) -> str:
    """대상 파일의 테스트를 작성·실행하고 결과를 반환합니다."""
    return str(tester(f"{path} 파일의 함수를 테스트해 주세요."))


if __name__ == "__main__":
    # Tester 단독 테스트 — 응답 마지막 줄이 passed=N failed=M 형식이어야 한다.
    result = run_tests("reservation.py")
    print(result)
