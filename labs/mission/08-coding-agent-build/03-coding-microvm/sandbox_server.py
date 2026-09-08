"""MicroVM 샌드박스 안에서 도는 FastAPI 서버 — /health, /run-tests 두 경로.

포트 8080. Dockerfile이 sandbox 사용자(비root)로 이 서버를 실행한다.
"""
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

SANDBOX = Path("/sandbox")
app = FastAPI()


class TestRequest(BaseModel):
    source_code: str
    source_filename: str
    test_code: str


@app.get("/health")
def health():
    """샌드박스 준비 상태와 런타임 버전을 반환합니다."""
    pytest_version = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {"status": "ok", "python": sys.version.split()[0], "pytest": pytest_version}


@app.post("/run-tests")
def run_tests(request: TestRequest):
    """소스와 테스트를 /sandbox에 쓰고 pytest를 실행합니다."""
    if request.source_code:
        (SANDBOX / request.source_filename).write_text(request.source_code)
    (SANDBOX / "test_code.py").write_text(request.test_code)

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "test_code.py", "--tb=short", "-q", "-s"],
        cwd=SANDBOX,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"output": completed.stdout + completed.stderr, "exitCode": completed.returncode}
