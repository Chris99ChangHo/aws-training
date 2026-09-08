"""MicroVM 실행·인증·호출·종료 헬퍼."""
from __future__ import annotations

import time

import boto3
import requests

REGION = "us-west-2"
IMAGE_ARN = "arn:aws:lambda:us-west-2:000000000000:microvm-image:python312-sandbox"
# 커넥터는 이름이 아니라 ARN이다. ALL_INGRESS는 다른 커넥터와 함께 쓸 수 없다
# (실제로 ValidationException 발생) — HTTP 호출은 HTTP_INGRESS, 셸 디버깅은
# SHELL_INGRESS로 조합한다.
HTTP_INGRESS_ARN = f"arn:aws:lambda:{REGION}:aws:network-connector:aws-network-connector:HTTP_INGRESS"
SHELL_INGRESS_ARN = f"arn:aws:lambda:{REGION}:aws:network-connector:aws-network-connector:SHELL_INGRESS"

microvms_client = boto3.client("lambda-microvms", region_name=REGION)


def create_sandbox() -> tuple[str, str]:
    """MicroVM을 실행하고 (microvm_id, endpoint)를 반환한다."""
    run_response = microvms_client.run_microvm(
        imageIdentifier=IMAGE_ARN,
        ingressNetworkConnectors=[HTTP_INGRESS_ARN, SHELL_INGRESS_ARN],
        idlePolicy={
            "maxIdleDurationSeconds": 300,
            "suspendedDurationSeconds": 600,
            "autoResumeEnabled": True,
        },
    )
    microvm_id = run_response["microvmId"]
    endpoint = run_response["endpoint"]
    print(f"MicroVM started: {microvm_id} ({run_response['state']})")

    while microvms_client.get_microvm(microvmIdentifier=microvm_id)["state"] == "PENDING":
        time.sleep(2)
    return microvm_id, endpoint


def get_auth_token(microvm_id: str, port: int = 8080) -> str:
    """엔드포인트 호출용 인증 토큰을 발급한다 (최대 60분)."""
    token_response = microvms_client.create_microvm_auth_token(
        microvmIdentifier=microvm_id,
        expirationInMinutes=30,
        allowedPorts=[{"port": port}],
    )
    return token_response["authToken"]["X-aws-proxy-auth"]


def run_tests_in_microvm(
    endpoint: str,
    auth_token: str,
    source_code: str,
    source_filename: str,
    test_code: str,
) -> dict:
    """MicroVM의 /run-tests를 호출해 pytest 결과를 받는다."""
    response = requests.post(
        f"https://{endpoint}/run-tests",
        headers={"X-aws-proxy-auth": auth_token},
        json={
            "source_code": source_code,
            "source_filename": source_filename,
            "test_code": test_code,
        },
        timeout=310,
    )
    response.raise_for_status()
    return response.json()


def destroy_sandbox(microvm_id: str) -> None:
    """MicroVM을 종료한다 — 메모리·디스크 상태가 함께 사라진다."""
    microvms_client.terminate_microvm(microvmIdentifier=microvm_id)
    print(f"MicroVM terminated: {microvm_id}")


if __name__ == "__main__":
    microvm_id, endpoint = create_sandbox()
    auth_token = get_auth_token(microvm_id)

    health = requests.get(
        f"https://{endpoint}/health",
        headers={"X-aws-proxy-auth": auth_token},
        timeout=30,
    )
    print(f"/health {health.status_code}: {health.json()}")

    result = run_tests_in_microvm(
        endpoint=endpoint,
        auth_token=auth_token,
        source_code="",
        source_filename="sample.py",
        test_code="def test_add(): assert 1+1 == 2\n",
    )
    print(f"pytest output:\n{result['output']}")

    destroy_sandbox(microvm_id)
