# Python 작성 규칙

기본은 [PEP 8](https://peps.python.org/pep-0008/)(코드 스타일),
[PEP 257](https://peps.python.org/pep-0257/)(docstring),
[PEP 484](https://peps.python.org/pep-0484/)(타입 힌트)를 따른다.
아래는 그중 자주 어긋나는 항목이다.

## 스타일 (PEP 8)

- 들여쓰기 4칸, 한 줄 최대 88자(Black 기본값).
- 네이밍: 함수·변수 `snake_case`, 클래스 `PascalCase`,
  모듈 상수 `UPPER_SNAKE_CASE`.
- import 순서: 표준 라이브러리 → 서드파티 → 로컬. 그룹 사이 빈 줄.
- 비교는 `is None` / `is not None`을 쓴다. `== None` 금지.

## 타입 힌트 (PEP 484 / PEP 563)

- 공개 함수의 인자와 반환값에 타입 힌트를 붙인다. 반환이 없으면 `-> None`.
- 파일 상단에 `from __future__ import annotations`를 두면
  `list[str]`, `dict | None` 같은 최신 문법을 하위 버전에서도 쓸 수 있다.

## docstring (PEP 257)

- 모듈·공개 함수·클래스에 docstring을 작성한다.
- 첫 줄은 명령형 한 문장 요약. 상세 설명은 빈 줄 뒤에 이어 쓴다.
- 주석은 "무엇"이 아니라 **"왜"**를 설명한다. 코드가 이미 무엇을 하는지
  말해주므로, 비자명한 판단·우회 처리의 이유를 남긴다.

## 에러 처리

- `except`는 구체적인 예외를 지정한다. 광범위한 `except Exception`은
  사용자에게 오류를 표시하는 최상단 경계에서만 쓰고 이유를 주석으로 남긴다.
- 예외를 삼키지 않는다. 잡았으면 로그를 남기거나 다시 raise한다.
- 재시도 로직에는 최대 횟수와 타임아웃을 명시한다. 무한 대기 금지.

## 의존성

- `requirements.txt`에 정확한 버전을 고정한다(`==`). 범위 지정(`>=`)은
  재현성을 깨뜨린다.
- 표준 라이브러리로 해결되는 일에는 외부 패키지를 추가하지 않는다.

## 실행 스크립트

- 엔트리포인트는 `main() -> int`로 두고 `raise SystemExit(main())`로
  종료 코드를 반환한다. 성공/실패를 종료 코드로 구분해 조합 가능하게 만든다.
- `if __name__ == "__main__":` 가드를 둔다.

## 파일 경로는 스크립트 위치 기준으로

읽고 쓰는 파일은 실행 위치(cwd)가 아니라 **스크립트 파일 위치**를 기준으로
해석한다.

```python
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "kb_info.json"
```

**이유**: `open("kb_info.json")`처럼 상대 경로를 쓴 스크립트가, 폴더가 깊어진
뒤 리포 루트에서 실행하니 `FileNotFoundError`로 깨졌다. 클론한 사람이 바로
밟는 함정이 된다. 쉘 쪽 대응 규칙은 `shell-conventions.md`의 "경로는 cwd가
아니라 대상 기준으로 해석한다"다.

## 도메인별 규칙은 스킬에 있다

- AWS 리소스를 만드는 실습 스크립트(멱등성, 환경별 식별자,
  `put_role_policy` 덮어쓰기 함정) → `aws-lab-conventions` 스킬
- `agents/` 아래 벤더 독립 에이전트(종료 코드 계약, 어댑터 생성물)
  → `agent-conventions` 스킬
