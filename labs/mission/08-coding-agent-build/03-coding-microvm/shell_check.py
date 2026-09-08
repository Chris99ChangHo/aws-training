"""셸은 서브프로토콜로 인증하고 포트 8022로 붙는다."""
from __future__ import annotations

import sys

import boto3
import websockets.sync.client

from sandbox_runner import create_sandbox, destroy_sandbox

REGION = "us-west-2"

microvms_client = boto3.client("lambda-microvms", region_name=REGION)


def main() -> int:
    microvm_id, endpoint = create_sandbox()
    try:
        shell_token = microvms_client.create_microvm_shell_auth_token(
            microvmIdentifier=microvm_id,
            expirationInMinutes=15,
        )["authToken"]["X-aws-proxy-auth"]

        with websockets.sync.client.connect(
            f"wss://{endpoint}/shell",
            subprotocols=[
                f"lambda-microvms.authentication.{shell_token}",
                "lambda-microvms",
                "lambda-microvms.port.8022",
            ],
        ) as ws:
            ws.send("whoami\n")
            # 첫 프레임은 session_init 메타데이터, 그 다음이 실제 명령 출력이다
            # (실제로 확인함 — 한 번만 받으면 init 메시지만 보인다).
            print(ws.recv(timeout=10))
            print(ws.recv(timeout=10))
        return 0
    finally:
        destroy_sandbox(microvm_id)


if __name__ == "__main__":
    sys.exit(main())
