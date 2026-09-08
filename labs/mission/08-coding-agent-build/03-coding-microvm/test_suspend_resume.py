"""suspend/resume 활용 (도전 과제) — 매번 종료하는 대신 suspend로 멈추고
다음 요청에 resume하면 pip install 캐시 등 상태가 유지되는지 비교한다.

주의: 커넥터는 실행 시점에 고정되어 재개 시 바꿀 수 없다.
"""
from __future__ import annotations

import time

from sandbox_runner import create_sandbox, destroy_sandbox, get_auth_token, microvms_client, run_tests_in_microvm


def install_and_check(endpoint: str, auth_token: str) -> str:
    """샌드박스에 패키지를 설치하고 import 가능 여부를 테스트로 확인한다."""
    result = run_tests_in_microvm(
        endpoint=endpoint,
        auth_token=auth_token,
        source_code="",
        source_filename="probe.py",
        test_code=(
            "import subprocess, sys\n"
            "def test_install_and_import():\n"
            "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'cowsay'], check=True)\n"
            "    import cowsay\n"
            "    assert cowsay is not None\n"
        ),
    )
    return result["output"]


def main() -> int:
    print("=== 1. MicroVM 실행 + 패키지 설치 ===")
    microvm_id, endpoint = create_sandbox()
    auth_token = get_auth_token(microvm_id)
    output_1 = install_and_check(endpoint, auth_token)
    print(output_1)

    print("\n=== 2. Suspend ===")
    microvms_client.suspend_microvm(microvmIdentifier=microvm_id)
    state = microvms_client.get_microvm(microvmIdentifier=microvm_id)["state"]
    print(f"상태: {state}")

    print("\n=== 3. Resume 후 같은 패키지 재확인 (캐시 유지 여부) ===")
    microvms_client.resume_microvm(microvmIdentifier=microvm_id)
    for _ in range(15):
        state = microvms_client.get_microvm(microvmIdentifier=microvm_id)["state"]
        if state == "RUNNING":
            break
        time.sleep(2)
    print(f"상태: {state}")

    # resume 후에는 엔드포인트가 바뀔 수 있으므로 다시 조회한다.
    microvm_info = microvms_client.get_microvm(microvmIdentifier=microvm_id)
    resumed_endpoint = microvm_info["endpoint"]

    output_2 = run_tests_in_microvm(
        endpoint=resumed_endpoint,
        auth_token=auth_token,
        source_code="",
        source_filename="probe2.py",
        test_code=(
            "def test_cached_import():\n"
            "    import cowsay  # pip install 없이 바로 되면 캐시가 유지된 것\n"
            "    assert cowsay is not None\n"
        ),
    )
    print(output_2["output"])

    destroy_sandbox(microvm_id)
    print("\n판정: 2번째 테스트가 pip install 없이 통과하면 suspend/resume 사이 상태(설치된 패키지)가 유지된 것입니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
