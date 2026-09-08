"""MicroVM 샌드박스 콘솔 — 코드를 입력하면 격리된 MicroVM에서 실행하고,
격리 증거(microvmId·hostname)를 함께 보여준다.
"""
import streamlit as st

from sandbox_runner import (
    create_sandbox,
    destroy_sandbox,
    get_auth_token,
    run_tests_in_microvm,
)
from test_isolation import shell_exec

st.set_page_config(page_title="MicroVM 샌드박스 콘솔", layout="wide")
st.title("MicroVM 샌드박스 콘솔")

col_source, col_test = st.columns(2)
source_code = col_source.text_area(
    "소스 코드", height=240, value="def validate_party_size(n):\n    return 1 <= n <= 20\n"
)
test_code = col_test.text_area(
    "테스트 코드",
    height=240,
    value="from reservation import validate_party_size\n\n"
    "def test_ok(): assert validate_party_size(4)\n"
    "def test_too_many(): assert not validate_party_size(21)\n",
)

if st.button("MicroVM에서 실행", type="primary"):
    with st.spinner("MicroVM 실행 중..."):
        microvm_id, endpoint = create_sandbox()
        auth_token = get_auth_token(microvm_id)
        try:
            result = run_tests_in_microvm(
                endpoint=endpoint,
                auth_token=auth_token,
                source_code=source_code,
                source_filename="reservation.py",
                test_code=test_code,
            )
            hostname = shell_exec(endpoint, auth_token, "cat /etc/hostname").strip()
        finally:
            destroy_sandbox(microvm_id)

    st.subheader("pytest 출력")
    st.code(result["output"], language="text")
    st.caption(f"exit code: {result['exitCode']}")

    st.sidebar.subheader("격리 증거")
    st.sidebar.write(f"**microvmId**: `{microvm_id}`")
    st.sidebar.write("**상태**: TERMINATED (실행 후 즉시 종료)")
    st.sidebar.write(f"**/etc/hostname**: `{hostname}`")
