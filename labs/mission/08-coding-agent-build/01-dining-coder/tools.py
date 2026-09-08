"""코딩 에이전트가 쓰는 도구 3종: 셸 실행, 파일 읽기, 파일 쓰기.

workspace/ 밖 경로 접근과 파괴적 명령을 거부한다. 거부는 예외가 아니라
반환값 문자열로 알려준다 — 예외로 죽으면 에이전트가 거부 이유를 모른 채
같은 시도를 반복한다.

도전 과제 3종 포함:
- READONLY=1 환경변수: write_file·run_shell을 거부 문자열로 분기
- ALLOWED_COMMANDS 환경변수(쉼표구분): 지정 시 명령 첫 토큰이 화이트리스트
  안에 있어야 실행 허용
- log_tool_call Hook: AfterToolCallEvent로 도구명·인자·반환값을
  workspace/.log에 append (Agent(hooks=[log_tool_call]) 형태로 등록)
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from strands import tool
from strands.hooks import AfterToolCallEvent

WORKSPACE = (Path(__file__).parent / "workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)

DANGEROUS_COMMANDS = ["rm -rf /", "sudo", ":(){", "mkfs", "dd if="]


def _safe_path(path: str) -> Path | None:
    """workspace 안이면 해석된 경로, 밖이면 None.

    resolve() 후 is_relative_to()로 판정해야 "../" 문자열 필터가 놓치는
    절대 경로·심링크 우회까지 함께 막을 수 있다.
    """
    target = (WORKSPACE / path).resolve()
    return target if target.is_relative_to(WORKSPACE) else None


def _is_readonly() -> bool:
    return os.environ.get("READONLY") == "1"


def _allowed_commands() -> list[str] | None:
    """ALLOWED_COMMANDS 환경변수가 설정되어 있으면 화이트리스트 목록을,
    설정 안 되어 있으면 None(제한 없음)을 반환한다."""
    raw = os.environ.get("ALLOWED_COMMANDS")
    if not raw:
        return None
    return [c.strip() for c in raw.split(",") if c.strip()]


@tool
def run_shell(command: str) -> str:
    """workspace를 작업 디렉터리(cwd)로 셸 명령을 실행합니다.

    cwd가 이미 workspace이므로 명령 안의 경로도 workspace 기준 상대 경로를
    씁니다 — 예: "python reservation.py" (workspace/reservation.py로 다시
    들어가지 않습니다).

    READONLY=1이면 거부합니다. ALLOWED_COMMANDS가 설정되어 있으면 명령의
    첫 토큰이 그 목록에 있어야 실행됩니다.
    """
    if _is_readonly():
        return f"거부: READONLY 모드에서는 셸 명령을 실행할 수 없습니다 — {command}"
    if any(bad in command for bad in DANGEROUS_COMMANDS):
        return f"거부: 파괴적인 명령으로 판단했습니다 — {command}"

    allowed = _allowed_commands()
    if allowed is not None:
        first_token = command.strip().split()[0] if command.strip() else ""
        if first_token not in allowed:
            return f"거부: '{first_token}'는 허용 명령 목록에 없습니다 — 허용: {', '.join(allowed)}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return f"중단: 60초 실행 상한을 넘겨 종료했습니다 — {command}"
    return f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


@tool
def read_file(path: str) -> str:
    """workspace 안의 파일을 읽습니다.

    path는 workspace 루트를 기준으로 한 상대 경로입니다 — 예: "reservation.py",
    "sub/utils.py". workspace 자체가 이미 루트이므로 "workspace/reservation.py"처럼
    workspace를 다시 접두어로 붙이지 마세요.
    """
    target = _safe_path(path)
    if target is None:
        return f"거부: {path}는 workspace 밖입니다. workspace 안 상대 경로만 허용됩니다."
    if not target.exists():
        return f"실패: {path} 파일이 존재하지 않습니다."
    return target.read_text(encoding="utf-8")


@tool
def write_file(path: str, content: str) -> str:
    """workspace 안의 파일에 내용을 씁니다.

    path는 workspace 루트를 기준으로 한 상대 경로입니다 — 예: "reservation.py",
    "sub/utils.py". workspace 자체가 이미 루트이므로 "workspace/reservation.py"처럼
    workspace를 다시 접두어로 붙이지 마세요.

    READONLY=1이면 거부합니다.
    """
    if _is_readonly():
        return f"거부: READONLY 모드에서는 파일을 쓸 수 없습니다 — {path}"
    target = _safe_path(path)
    if target is None:
        return f"거부: {path}는 workspace 밖입니다. workspace 안 상대 경로만 허용됩니다."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"작성 완료: {target.relative_to(WORKSPACE)} ({len(content)} bytes)"


def log_tool_call(event: AfterToolCallEvent) -> None:
    """AfterToolCallEvent Hook — 도구명·인자·반환값을 workspace/.log에 append.

    Agent(hooks=[log_tool_call])로 등록한다. 실패해도 에이전트 실행을
    막지 않도록 로그 기록 자체의 예외는 삼킨다(단, 원인 파악용으로
    stderr에는 남긴다).
    """
    try:
        tool_use = getattr(event, "tool_use", {}) or {}
        result = getattr(event, "result", None)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool_use.get("name"),
            "input": tool_use.get("input"),
            "result": str(result)[:500] if result is not None else None,
        }
        log_path = WORKSPACE / ".log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 - 로깅 실패가 본 작업을 막으면 안 됨
        import sys

        print(f"log_tool_call 기록 실패(무시): {exc}", file=sys.stderr)


if __name__ == "__main__":
    # 경계 테스트 — 직접 실행해 도구 동작을 눈으로 확인한다.
    print(write_file("../escape.txt", "x"))       # 거부
    print(write_file("test.txt", "hello world"))  # 성공
    print(read_file("test.txt"))                  # 성공
    print(run_shell("rm -rf /"))                  # 거부
    print(run_shell("echo OK"))                   # 성공

    # 도전 과제 1: READONLY 모드
    os.environ["READONLY"] = "1"
    print(write_file("readonly-test.txt", "x"))    # 거부 (READONLY)
    print(run_shell("echo blocked"))               # 거부 (READONLY)
    del os.environ["READONLY"]

    # 도전 과제 2: 명령 화이트리스트
    os.environ["ALLOWED_COMMANDS"] = "python,pytest,ls"
    print(run_shell("ls"))                         # 성공 (화이트리스트 포함)
    print(run_shell("curl https://example.com"))   # 거부 (화이트리스트 밖)
    del os.environ["ALLOWED_COMMANDS"]

