# 쉘 작성 규칙

기본은 [POSIX Shell Command Language](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html)
(IEEE 1003.1)를 따른다. 아래는 `agents/security/scanners/`의 쉘 1,126줄에서
실제로 문제가 됐거나, 그 코드가 이미 지켜서 규칙으로 굳힌 항목이다.

## POSIX sh로 쓴다

셔뱅은 `#!/bin/sh`. bash 확장(`local`, `[[ ]]`, 배열, `$'...'`)을 쓰지 않는다.
꼭 필요하면 `#!/bin/bash`로 **명시**하고 이유를 주석으로 남긴다.

**이유**: `/bin/sh`의 실체는 OS마다 다르다(dash, bash의 POSIX 모드 등). 확장
문법은 개발 머신에서 통과하고 다른 환경에서 깨진다
([SC2039](https://www.shellcheck.net/wiki/SC2039)).

## `set -u`는 쓰고 `set -e`는 쓰지 않는다

```sh
set -u   # 정의되지 않은 변수 참조를 즉시 실패로
```

`set -e`는 **금지**한다. 종료 코드로 상태를 구분하는 스크립트에서 정상 신호를
오류로 오인해 파이프라인을 중단시킨다. 실측 근거: 스캐너는 발견이 있으면 1을
반환하기도 하는데(Semgrep), `set -e` 파이프라인은 첫 발견에서 중단되고 나머지
스캐너를 조용히 건너뛴다(`agents/security/scanners/_lib.sh` 주석).

에러 처리는 호출 지점에서 명시한다.

```sh
mkdir -p "$REPORT_DIR" || {
    log "cannot create report directory: $REPORT_DIR"
    exit "$EXIT_SCAN_ERROR"
}
```

## 종료 코드는 상수로 선언한다

숫자 리터럴을 `exit`에 직접 쓰지 않는다. 이름이 있어야 호출자가 계약을 읽을 수
있고, 값을 바꿀 때 한 곳만 고친다.

```sh
EXIT_OK=0
EXIT_TOOL_MISSING=3
EXIT_SCAN_ERROR=4
```

계약 자체(0/1/2/3/4의 뜻)는 `agent-conventions` 스킬에 있다.

## 도구 존재 확인은 `command -v`로

`which`는 POSIX가 아니고 쉘 내장 명령을 못 찾는다.

```sh
command -v "$1" >/dev/null 2>&1 || die_missing "$1"
```

## 변수 확장은 큰따옴표로 감싼다

예외는 **의도적인 단어 분할**뿐이고, 이때는 글로브 확장을 끄고 범위를 좁힌다.

```sh
set -f
# shellcheck disable=SC2086
set -- $CMD
set +f
```

`set -f`가 없으면 `*.txt` 같은 토큰이 현재 디렉토리에 대해 확장되어, 실제로
입력된 인자가 아니라 파일명을 검사하게 된다
([SC2086](https://www.shellcheck.net/wiki/SC2086)).

## 경로는 cwd가 아니라 대상 기준으로 해석한다

패턴·경로를 실행 위치에 의존하게 두면 같은 명령이 실행 위치에 따라 다른 결과를
낸다. 실측: Trivy의 `--skip-dirs` glob이 스캔 대상이 아니라 cwd에 대해 해석돼
**같은 명령이 12건 대 63건**으로 갈렸다(`run_sca.sh`).

```sh
ABS_TARGET=$(cd "$TARGET" && pwd)
```

Python 쪽 대응 규칙은 `python-conventions.md`의 "파일 경로는 스크립트 위치
기준으로"다.

## stdout은 데이터, 로그는 stderr

stdout을 파이프로 받는 호출자가 있으므로 진단 출력을 섞지 않는다. `echo` 대신
`printf`를 쓴다 — `echo`는 백슬래시·`-n` 처리가 구현마다 다르다.

```sh
log() {
    printf '[%s] %s\n' "${WRAPPER_NAME:-sec}" "$*" >&2
}
```

## 아직 정하지 않은 것

- **줄 길이 상한.** Python은 88자인데 쉘은 61줄이 88자를 넘는다(`agents/` 전량
  실측). 상한을 정하면 기존 코드를 대량 수정해야 하므로 강제하지 않는다.
- **ShellCheck 강제.** 코드에 지시 주석은 있으나 로컬에 미설치다. CI를 만드는
  시점에 종료 코드 게이트로 함께 넣는다.
