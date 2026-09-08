"""Reviewer 에이전트 — 코드 품질을 읽기만 하고 판정한다 (쓰기 도구 없음).

Reviewer에게 쓰기 도구를 주면 지적 대신 직접 고쳐버려 Coder에게 갈 학습
신호가 사라진다. 그래서 read_file만 준다.

도전 과제(합의 규칙): 품질 리뷰어(review_code)와 보안 리뷰어
(review_security)를 분리해 둔다 — 둘 다 APPROVED일 때만 통과시키는
합의 규칙은 orchestrator.py에서 구성한다.
"""
from __future__ import annotations

from strands import Agent, tool
from strands.models import BedrockModel

from tools import read_file

REVIEWER_SYSTEM_PROMPT = """당신은 코드 리뷰어입니다. 다음 기준으로 검토합니다:
1. 경계값 처리 (수용 인원과 정확히 같은 인원 등)
2. 잘못된 입력 처리 (0명, 음수, 없는 식당)
3. 함수 분리 (단일 책임)
4. 이름의 명확성

중요: 다른 설명 없이 응답의 맨 첫 줄을 정확히 APPROVED 또는
NEEDS_CHANGES로만 시작하세요. "네, 확인하겠습니다" 같은 서두 문장을
앞에 붙이지 마세요. NEEDS_CHANGES면 그 다음 줄부터 고칠 항목을
번호로 나열하세요."""

SECURITY_REVIEWER_SYSTEM_PROMPT = """당신은 보안 리뷰어입니다. 다음 기준으로 검토합니다:
1. 인젝션 위험 (eval·exec·os.system·문자열 포맷으로 만든 셸/SQL 명령)
2. 입력 검증 누락 (외부에서 온 값을 검증 없이 신뢰하는지)
3. 예외 처리로 민감 정보(경로·스택트레이스)를 그대로 노출하는지
4. 하드코딩된 자격 증명·비밀값

중요: 다른 설명 없이 응답의 맨 첫 줄을 정확히 APPROVED 또는
NEEDS_CHANGES로만 시작하세요. 서두 문장을 앞에 붙이지 마세요.
NEEDS_CHANGES면 그 다음 줄부터 고칠 항목을 번호로 나열하세요."""

reviewer = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name="us-west-2"),
    system_prompt=REVIEWER_SYSTEM_PROMPT,
    tools=[read_file],
)

security_reviewer = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name="us-west-2"),
    system_prompt=SECURITY_REVIEWER_SYSTEM_PROMPT,
    tools=[read_file],
)


@tool
def review_code(path: str) -> str:
    """지정한 파일의 코드 품질을 검토하고 판정을 반환합니다."""
    return str(reviewer(f"{path} 파일의 코드를 검토해 주세요."))


@tool
def review_security(path: str) -> str:
    """지정한 파일의 보안 위험을 검토하고 판정을 반환합니다."""
    return str(security_reviewer(f"{path} 파일의 보안 위험을 검토해 주세요."))


if __name__ == "__main__":
    # Reviewer 단독 테스트 — 응답 첫 줄이 APPROVED/NEEDS_CHANGES로 시작해야 한다.
    result = review_code("reservation.py")
    print(result)
    print("---보안 리뷰---")
    print(review_security("reservation.py"))
