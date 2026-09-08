"""코디네이터 — Coder·Reviewer·Tester를 파이썬 코드로 조율한다.

루프 카운터·종료 조건은 코드가 판정한다. "3회까지만"을 프롬프트로
지시하면 모델이 셈을 놓쳐 계속 돌거나 1회로 끝난다.
"""
from __future__ import annotations

import logging
import re

from strands import Agent, tool
from strands.models import BedrockModel

from reviewer import review_code, review_security
from tester import run_tests
from tools import read_file, run_shell, write_file

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MAX_ROUNDS = 3

# Tester가 "마지막 줄에 passed=N failed=M"을 지시받아도, 그 뒤에 요약 표 같은
# 부연 설명을 덧붙이면 실제 마지막 줄이 그 표의 행이 되어 split("\n")[-1]로는
# 못 찾는다. 출력 전체에서 패턴을 찾아 마지막 매치를 쓰는 쪽이 더 견고하다.
_PASSED_FAILED_RE = re.compile(r"passed=(\d+)\s+failed=(\d+)")

# Reviewer 응답은 "네, 먼저 확인하겠습니다... ## APPROVED" 처럼 서두 잡담과
# 마크다운 헤더가 판정 키워드 앞에 붙는다. strip().startswith()로는 못 잡으므로
# 응답 전체에서 먼저 등장하는 판정 키워드를 찾는다.
_REVIEW_VERDICT_RE = re.compile(r"\b(APPROVED|NEEDS_CHANGES)\b")


def _parse_test_result(test_output: str) -> tuple[bool, str]:
    """테스트 출력에서 passed=N failed=M 패턴을 찾아 통과 여부를 판정한다.

    패턴을 찾지 못하면 형식 불일치로 보고 미통과 처리한다 (폴백).
    """
    matches = list(_PASSED_FAILED_RE.finditer(test_output))
    if not matches:
        return False, "형식 불일치: passed=N failed=M 패턴을 찾지 못함"
    passed, failed = matches[-1].groups()
    summary = f"passed={passed} failed={failed}"
    return failed == "0", summary


def _parse_review_verdict(review: str) -> bool:
    """리뷰 응답에서 APPROVED/NEEDS_CHANGES 판정을 찾는다.

    판정 키워드를 찾지 못하면 형식 불일치로 보고 미승인 처리한다 (폴백).
    """
    match = _REVIEW_VERDICT_RE.search(review)
    return match is not None and match.group(1) == "APPROVED"

# --- Coder 에이전트 ---
coder = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name="us-west-2"),
    system_prompt="당신은 파이썬 개발자입니다. workspace/ 디렉토리에 코드를 작성합니다.",
    tools=[read_file, write_file, run_shell],
)


@tool
def write_code(task: str) -> str:
    """Coder에게 코드 작성을 요청합니다."""
    return str(coder(task))


def build_with_review(task: str) -> dict:
    """자기 교정 루프 — 최대 3회 재작업.

    합의 규칙(도전 과제): 품질 리뷰어와 보안 리뷰어 둘 다 APPROVED이고
    Tester도 failed=0일 때만 통과시킨다. 회차별 토큰 사용량(도전 과제:
    비용 측정)도 함께 기록한다.
    """
    feedback = ""
    code = ""
    history: list[dict] = []

    for round_no in range(1, MAX_ROUNDS + 1):
        # Coder 호출 — 재작업 시 피드백 원문을 그대로 전달한다 (요약하지 않음).
        prompt = task
        if feedback:
            prompt = f"{task}\n\n지난 회차 지적 사항 (원문 그대로):\n{feedback}"
        code = str(write_code(prompt))
        logger.info("round=%s Coder 완료", round_no)

        # 품질 리뷰어 판정
        review = str(review_code("reservation.py")).strip()
        approved_quality = _parse_review_verdict(review)
        logger.info("round=%s approved_quality=%s", round_no, approved_quality)

        # 보안 리뷰어 판정 — 합의 규칙: 둘 다 APPROVED여야 통과
        security_review = str(review_security("reservation.py")).strip()
        approved_security = _parse_review_verdict(security_review)
        logger.info("round=%s approved_security=%s", round_no, approved_security)

        approved = approved_quality and approved_security

        # Tester 판정
        test_output = str(run_tests("reservation.py")).strip()
        passed, summary = _parse_test_result(test_output)
        logger.info("round=%s passed=%s (%s)", round_no, passed, summary)

        token_usage = _collect_token_usage()
        logger.info("round=%s token_usage=%s", round_no, token_usage)

        history.append(
            {
                "round": round_no,
                "approved_quality": approved_quality,
                "approved_security": approved_security,
                "approved": approved,
                "passed": passed,
                "review": review,
                "security_review": security_review,
                "test": summary,
                "token_usage": token_usage,
            }
        )

        if approved and passed:
            return {"state": "APPROVED", "rounds": round_no, "code": code, "history": history}

        feedback = (
            f"[품질 리뷰 판정]\n{review}\n\n"
            f"[보안 리뷰 판정]\n{security_review}\n\n"
            f"[테스트 결과]\n{test_output}"
        )

    return {
        "state": "BEST_EFFORT",
        "history": history,
        "rounds": MAX_ROUNDS,
        "code": code,
        "remaining": feedback,
    }


def _collect_token_usage() -> dict:
    """Coder·Reviewer·Tester 각 에이전트의 누적 토큰 사용량을 모은다
    (도전 과제: 비용 측정). event_loop_metrics가 없는 구버전 호환을 위해
    getattr로 방어한다.
    """
    from reviewer import reviewer, security_reviewer
    from tester import tester

    def _usage(agent) -> dict:
        metrics = getattr(agent, "event_loop_metrics", None)
        usage = getattr(metrics, "accumulated_usage", None) if metrics else None
        if not usage:
            return {}
        return dict(usage)

    return {
        "coder": _usage(coder),
        "reviewer": _usage(reviewer),
        "security_reviewer": _usage(security_reviewer),
        "tester": _usage(tester),
    }


if __name__ == "__main__":
    result = build_with_review(
        "예약 인원 검증 함수를 경계값과 잘못된 입력까지 처리하도록 만들어 주세요"
    )
    print(f"최종 상태: {result['state']} (라운드: {result['rounds']})")
