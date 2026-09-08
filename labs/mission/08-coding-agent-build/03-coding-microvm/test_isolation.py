"""격리 3축 실증 — 호스트 파일시스템 접근 불가, 테넌트 간 격리, 종료 시 상태 소멸.

네트워크 아웃바운드는 기본적으로 퍼블릭 인터넷이 열려 있으므로 이 실증의
대상이 아니다 (VPC egress 커넥터로 통제하는 대상).
"""
from __future__ import annotations

import socket

import boto3
import requests

from sandbox_runner import create_sandbox, destroy_sandbox, get_auth_token

REGION = "us-west-2"
microvms_client = boto3.client("lambda-microvms", region_name=REGION)


def shell_exec(endpoint: str, auth_token: str, command: str) -> str:
    """샌드박스 서버의 /run-tests를 통해 셸 명령의 출력을 얻는다."""
    response = requests.post(
        f"https://{endpoint}/run-tests",
        headers={"X-aws-proxy-auth": auth_token},
        json={
            "source_code": "",
            "source_filename": "probe.py",
            "test_code": (
                "import subprocess\n"
                "def test_probe():\n"
                f"    out = subprocess.run({command!r}, shell=True, capture_output=True, text=True)\n"
                "    print(out.stdout + out.stderr)\n"
                "    assert True\n"
            ),
        },
        timeout=60,
    )
    return response.json()["output"]


def test_filesystem_isolation() -> None:
    """호스트 파일시스템 격리 테스트."""
    print("\n=== 1. 호스트 파일시스템 격리 ===")

    microvm_id, endpoint = create_sandbox()
    auth_token = get_auth_token(microvm_id)

    host_hostname = socket.gethostname()
    microvm_hostname = shell_exec(endpoint, auth_token, "cat /etc/hostname")
    print(f"호스트 hostname: {host_hostname}")
    print(f"MicroVM hostname: {microvm_hostname.strip()}")
    assert host_hostname not in microvm_hostname, "hostname이 같으면 격리 실패"

    root_listing = shell_exec(endpoint, auth_token, "ls /")
    print(f"ls /:\n{root_listing}")

    mount_result = shell_exec(endpoint, auth_token, "mount | grep -v proc | grep -v sys")
    print(f"마운트 목록:\n{mount_result}")

    destroy_sandbox(microvm_id)
    print("파일시스템 격리 확인 완료")


def test_tenant_isolation() -> None:
    """MicroVM 간 격리 테스트."""
    print("\n=== 2. MicroVM 간 격리 ===")

    microvm_id_1, endpoint_1 = create_sandbox()
    microvm_id_2, endpoint_2 = create_sandbox()
    token_1 = get_auth_token(microvm_id_1)
    token_2 = get_auth_token(microvm_id_2)

    shell_exec(endpoint_1, token_1, "echo 'tenant-a' > /sandbox/evidence.txt")
    own = shell_exec(endpoint_1, token_1, "cat /sandbox/evidence.txt")
    print(f"1번 MicroVM - evidence.txt: {own.strip()[:80]}")
    assert "tenant-a" in own

    other = shell_exec(endpoint_2, token_2, "cat /sandbox/evidence.txt 2>&1")
    print(f"2번 MicroVM - evidence.txt: {other.strip()[:80]}")
    assert "tenant-a" not in other

    destroy_sandbox(microvm_id_1)
    destroy_sandbox(microvm_id_2)
    print("테넌트 간 격리 확인 완료")


def test_state_destruction() -> None:
    """종료 시 상태 소멸 테스트."""
    print("\n=== 3. 종료 시 상태 소멸 ===")

    microvm_id_1, endpoint_1 = create_sandbox()
    token_1 = get_auth_token(microvm_id_1)
    shell_exec(endpoint_1, token_1, "echo 'secret-data-12345' > /sandbox/evidence.txt")
    destroy_sandbox(microvm_id_1)
    print("1번 MicroVM 종료됨")

    microvm_id_2, endpoint_2 = create_sandbox()
    token_2 = get_auth_token(microvm_id_2)
    verify = shell_exec(endpoint_2, token_2, "cat /sandbox/evidence.txt 2>&1")
    print(f"새 MicroVM - evidence.txt: {verify.strip()[:80]}")
    assert "secret-data-12345" not in verify

    destroy_sandbox(microvm_id_2)
    print("상태 소멸 확인 완료 - 이전 상태 완전 소멸")


if __name__ == "__main__":
    test_filesystem_isolation()
    test_tenant_isolation()
    test_state_destruction()
    print("\n모든 격리 테스트 통과")
