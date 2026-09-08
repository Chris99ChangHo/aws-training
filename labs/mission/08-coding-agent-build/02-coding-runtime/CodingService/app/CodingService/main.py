"""CodingService — 팀 코딩 서비스 엔트리포인트.

1·2단계(01-dining-coder/)의 Coder·Reviewer·Tester 3에이전트 자기 교정
루프를 그대로 포팅한다. 새 패턴을 발명하지 않는다.

이 엔트리포인트는 단순 request/response 계약을 쓴다 — 프롬프트를 받아
루프를 돌리고 {"result": "..."} 를 반환한다. Shell Command
(InvokeAgentRuntimeCommand)로 오는 git 작업은 이 엔트리포인트를 거치지
않고 세션의 셸에서 직접 실행된다.
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
from datetime import timezone
from pathlib import Path

import botocore.auth
import botocore.awsrequest
import botocore.compat
import botocore.session
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

PERSISTENT = Path("/mnt/persistent")

MODEL_ID = "us.anthropic.claude-sonnet-4-6"
REGION = "us-west-2"

MAX_ROUNDS = 3


def _resolve_workspace() -> Path:
    """쓰기 가능한 workspace 경로를 찾는다.

    /workspace가 Runtime 컨테이너에서 항상 쓰기 가능하다고 보장되지
    않는다 — 실제로 이 배포에서는 PermissionError가 났다(로그 확인 완료).
    /var/task(배포 코드 위치)도 읽기 전용이다. Lambda 계열 런타임에서
    쓰기가 보장되는 경로는 /tmp뿐이므로 이를 우선 사용하고, 그마저 안
    되는 완전히 다른 환경(로컬 등)에서는 프로젝트 하위 폴더로 최종
    폴백한다.
    """
    candidates = [Path("/workspace"), Path("/tmp/workspace"), Path(__file__).parent / ".local-workspace"]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-probe"
            probe.write_text("ok")
            probe.unlink()
            return candidate
        except OSError:
            continue
    # 마지막 후보(.local-workspace)까지 실패하면 더 이상 폴백이 없다.
    raise RuntimeError("쓰기 가능한 workspace 경로를 찾지 못했습니다.")


WORKSPACE = _resolve_workspace()


# ── 도구 3종 — 1·2단계(01-dining-coder/tools.py)와 동일한 경계 규칙 ──
DANGEROUS_COMMANDS = ["rm -rf /", "sudo", ":(){", "mkfs", "dd if="]


def _safe_path(path: str) -> Path | None:
    target = (WORKSPACE / path).resolve()
    return target if target.is_relative_to(WORKSPACE) else None


@tool
def run_shell(command: str) -> str:
    """workspace를 작업 디렉터리(cwd)로 셸 명령을 실행합니다.

    cwd가 이미 workspace이므로 명령 안의 경로도 workspace 기준 상대 경로를
    씁니다.
    """
    if any(bad in command for bad in DANGEROUS_COMMANDS):
        return f"거부: 파괴적인 명령으로 판단했습니다 — {command}"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "오류: 명령 실행 시간 초과 (120초)"
    output = result.stdout + result.stderr
    return output if output.strip() else f"(exit {result.returncode})"


@tool
def read_file(path: str) -> str:
    """workspace 안의 파일을 읽습니다.

    path는 workspace 루트 기준 상대 경로입니다 — "workspace/"를 다시
    붙이지 마세요.
    """
    target = _safe_path(path)
    if target is None:
        return f"거부: workspace 밖 경로 '{path}'"
    if not target.exists():
        return f"오류: 파일 없음 '{path}'"
    return target.read_text(encoding="utf-8")


@tool
def write_file(path: str, content: str) -> str:
    """workspace 안에 파일을 씁니다.

    path는 workspace 루트 기준 상대 경로입니다 — "workspace/"를 다시
    붙이지 마세요.
    """
    target = _safe_path(path)
    if target is None:
        return f"거부: workspace 밖 경로 '{path}'"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"저장 완료: {path}"


# ── Coder·Reviewer·Tester — 역할별 도구를 다르게 준다 ──
CODER_SYSTEM_PROMPT = """당신은 파이썬 개발자입니다. workspace/ 디렉토리에 코드를 작성합니다.
파일을 작성한 뒤에는 반드시 run_shell로 실행해 결과를 확인합니다."""

REVIEWER_SYSTEM_PROMPT = """당신은 코드 리뷰어입니다. 다음 기준으로 검토합니다:
1. 경계값 처리
2. 잘못된 입력 처리
3. 함수 분리 (단일 책임)
4. 이름의 명확성

중요: 다른 설명 없이 응답의 맨 첫 줄을 정확히 APPROVED 또는
NEEDS_CHANGES로만 시작하세요. 서두 문장을 앞에 붙이지 마세요.
NEEDS_CHANGES면 그 다음 줄부터 고칠 항목을 번호로 나열하세요."""

TESTER_SYSTEM_PROMPT = """당신은 테스트 엔지니어입니다. 검증 대상 함수의 테스트를 작성해
저장하고 실행합니다. 경계값, 잘못된 입력, 정상 케이스를 모두 포함하세요.
pytest 실행이 끝나면 결과를 요약 없이 정확히 "passed=N failed=M" 한 줄로
보고하세요. 이 줄이 응답의 가장 마지막 내용이어야 합니다."""

TEAM_SYSTEM_PROMPT = """당신은 팀 코딩 에이전트입니다.
자연어 코딩 요청을 받아 코드를 작성하고 테스트합니다.
workspace 안에서만 작업하고, 완료 후 결과를 보고합니다.
git clone·push가 필요하면 먼저 get_codecommit_url 도구로 인증된 URL을
받아 그 URL로 git 명령을 실행하세요 (자격 증명을 직접 다루지 않습니다).

중요: 요청받은 범위만 작업하세요. 요청에 없는 추가 리팩토링, 기존 테스트
전체 재작성, 광범위한 검증은 하지 마세요. 작성한 코드가 문법적으로
올바른지 1회 실행으로 확인했으면 그것으로 충분합니다."""

_PASSED_FAILED_RE = re.compile(r"passed=(\d+)\s+failed=(\d+)")
_REVIEW_VERDICT_RE = re.compile(r"\b(APPROVED|NEEDS_CHANGES)\b")


def _codecommit_website_domain(region: str) -> str:
    return "amazonaws.com.cn" if region in ("cn-north-1", "cn-northwest-1") else "amazonaws.com"


def _sign_codecommit_request(hostname: str, path: str, region: str, credentials) -> str:
    """git-remote-codecommit과 동일한 SigV4 서명 방식으로 CodeCommit Git 인증
    서명을 만든다.

    Runtime 컨테이너에는 git-remote-codecommit이 설치되어 있지 않다 — PyPI에
    wheel이 없는 sdist-only 패키지라 AgentCore CDK의 --only-binary 패키징
    파이프라인에 넣을 수 없다(실제로 겪은 문제). botocore는 이미 의존성으로
    포함되어 있으므로, git-remote-codecommit의 서명 로직을 그대로 옮겨와
    표준 HTTPS git URL에 자격 증명을 인코딩한다.
    """
    request = botocore.awsrequest.AWSRequest(method="GIT", url=f"https://{hostname}{path}")
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    request.context["timestamp"] = timestamp

    signer = botocore.auth.SigV4Auth(credentials, "codecommit", region)
    canonical_request = f"GIT\n{path}\n\nhost:{hostname}\n\nhost\n"
    string_to_sign = signer.string_to_sign(request, canonical_request)
    signature = signer.signature(string_to_sign, request)
    return f"{timestamp}Z{signature}"


@tool
def get_codecommit_url(repository_name: str) -> str:
    """CodeCommit 리포지토리에 git clone/push할 수 있는 인증된 HTTPS URL을
    반환합니다. Runtime 실행 역할의 자격 증명으로 서명합니다.
    """
    session = botocore.session.Session()
    credentials = session.get_credentials()
    if credentials is None:
        return "오류: AWS 자격 증명을 찾지 못했습니다."

    hostname = f"git-codecommit.{REGION}.{_codecommit_website_domain(REGION)}"
    path = f"/v1/repos/{repository_name}"

    token = f"%{credentials.token}" if credentials.token else ""
    username = botocore.compat.quote(credentials.access_key + token, safe="")
    signature = _sign_codecommit_request(hostname, path, REGION, credentials)

    return f"https://{username}:{signature}@{hostname}{path}"


def _parse_test_result(test_output: str) -> tuple[bool, str]:
    matches = list(_PASSED_FAILED_RE.finditer(test_output))
    if not matches:
        return False, "형식 불일치: passed=N failed=M 패턴을 찾지 못함"
    passed, failed = matches[-1].groups()
    return failed == "0", f"passed={passed} failed={failed}"


def _parse_review_verdict(review: str) -> bool:
    match = _REVIEW_VERDICT_RE.search(review)
    return match is not None and match.group(1) == "APPROVED"


def _make_model() -> BedrockModel:
    return BedrockModel(model_id=MODEL_ID, region_name=REGION)


def build_with_review(task: str, target_path: str) -> dict:
    """Coder→Reviewer→Tester 자기 교정 루프. 최대 3회 재작업.

    01-dining-coder/orchestrator.py와 동일한 패턴 — 루프 카운터·판정은
    코드가 관리한다.
    """
    coder = Agent(model=_make_model(), system_prompt=CODER_SYSTEM_PROMPT, tools=[read_file, write_file, run_shell])
    reviewer = Agent(model=_make_model(), system_prompt=REVIEWER_SYSTEM_PROMPT, tools=[read_file])
    tester = Agent(model=_make_model(), system_prompt=TESTER_SYSTEM_PROMPT, tools=[write_file, run_shell])

    feedback = ""
    code = ""
    history: list[dict] = []

    for round_no in range(1, MAX_ROUNDS + 1):
        prompt = task
        if feedback:
            prompt = f"{task}\n\n지난 회차 지적 사항 (원문 그대로):\n{feedback}"
        code = str(coder(prompt))

        review = str(reviewer(f"{target_path} 파일의 코드를 검토해 주세요.")).strip()
        approved = _parse_review_verdict(review)

        test_output = str(tester(f"{target_path} 파일의 함수를 테스트해 주세요.")).strip()
        passed, summary = _parse_test_result(test_output)

        history.append({"round": round_no, "approved": approved, "passed": passed, "review": review, "test": summary})

        if approved and passed:
            return {"state": "APPROVED", "rounds": round_no, "code": code, "history": history}

        feedback = f"[리뷰 판정]\n{review}\n\n[테스트 결과]\n{test_output}"

    return {"state": "BEST_EFFORT", "history": history, "rounds": MAX_ROUNDS, "code": code, "remaining": feedback}


def append_work_log(request: str, result: str) -> None:
    """작업 로그를 영속 경로(S3 Files 마운트)에 기록한다.

    /mnt/persistent가 마운트되지 않은 환경에서는 조용히 건너뛴다 —
    로그 실패가 본 작업을 막으면 안 된다.
    """
    if not PERSISTENT.exists():
        return
    log_path = PERSISTENT / "work-log.json"
    logs = json.loads(log_path.read_text()) if log_path.exists() else []
    logs.append(
        {
            "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
            "request": request,
            "result": result[:500],
        }
    )
    log_path.write_text(json.dumps(logs, ensure_ascii=False, indent=2))


# git clone/push 같은 Shell Command 세션 준비 요청은 team_agent로 처리한다.
# 세션마다(요청마다) 새 인스턴스를 만든다 — Strands Agent는 동시 호출을
# 지원하지 않고(ConcurrencyException: 실제로 겪음), 전역 공유 인스턴스는
# 같은 컨테이너에서 처리되는 다른 세션의 요청과 충돌할 수 있다.
def _make_team_agent() -> Agent:
    return Agent(
        model=_make_model(),
        system_prompt=TEAM_SYSTEM_PROMPT,
        tools=[run_shell, read_file, write_file, get_codecommit_url],
    )


app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    prompt = payload.get("prompt", "")
    target_path = payload.get("target_path", "")

    if target_path:
        # 리뷰·테스트 자기 교정 루프 — target_path 파일을 대상으로 Coder/
        # Reviewer/Tester를 순환시킨다.
        loop_result = build_with_review(prompt, target_path)
        result_text = (
            f"[{loop_result['state']}] {loop_result['rounds']}라운드\n\n{loop_result['code']}"
        )
    else:
        # 단순 요청 — 팀 에이전트가 1회 처리 (git 작업 준비, 잡담성 요청 등)
        result_text = str(_make_team_agent()(prompt))

    append_work_log(request=prompt, result=result_text)
    return {"result": result_text}


if __name__ == "__main__":
    app.run()
