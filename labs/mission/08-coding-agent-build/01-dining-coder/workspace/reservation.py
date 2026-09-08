"""
reservation.py
==============
예약 인원 검증 모듈

검증 규칙
---------
- 인원은 정수(int)여야 합니다.
- 최소 인원 : GuestRule.min_guests =  1  (경계값 포함)
- 최대 인원 : GuestRule.max_guests = 20  (경계값 포함)
- None, 문자열, 실수, 리스트 등 비정수 타입은 모두 거부합니다.
- 숫자처럼 생긴 문자열("5")도 자동 변환 없이 거부합니다.
- bool 은 int 의 서브클래스이지만 예약 인원으로 허용하지 않습니다.
- 시스템 극단값(sys.maxsize, -sys.maxsize)도 범위 초과로 정상 처리합니다.

공개 API
--------
validate_guest_count(guests, rule?)  → int              예외 발생형
check_guest_count(guests, rule?)     → ValidationResult 예외 없는 래퍼
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# 1. 검증 규칙 (단일 진실 공급원)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GuestRule:
    """
    예약 인원에 관한 검증 규칙을 한 곳에서 관리합니다.

    Attributes
    ----------
    min_guests : int
        허용 최소 인원 (기본 1, 경계값 포함).
    max_guests : int
        허용 최대 인원 (기본 20, 경계값 포함).

    Raises
    ------
    TypeError
        min_guests 또는 max_guests 가 int(순수 정수)가 아닌 경우.
    ValueError
        min_guests < 1 이거나 max_guests < min_guests 인 경우.
    """

    min_guests: int = 1
    max_guests: int = 20

    def __post_init__(self) -> None:
        # ── 타입 검사: bool 은 int 서브클래스이므로 명시 차단 ─────────────
        for attr_name, attr_val in (
            ("min_guests", self.min_guests),
            ("max_guests", self.max_guests),
        ):
            if isinstance(attr_val, bool) or not isinstance(attr_val, int):
                raise TypeError(
                    f"{attr_name} 는 순수 int 여야 합니다. "
                    f"입력된 타입: {type(attr_val).__name__!r}"
                )

        # ── 값 범위 검사 ──────────────────────────────────────────────────
        if self.min_guests < 1:
            raise ValueError(
                f"min_guests 는 1 이상이어야 합니다. 현재 값: {self.min_guests}"
            )
        if self.max_guests < self.min_guests:
            raise ValueError(
                f"max_guests({self.max_guests}) 는 "
                f"min_guests({self.min_guests}) 이상이어야 합니다."
            )

    @property
    def range_description(self) -> str:
        """'1~20명' 형태의 범위 설명 문자열을 반환합니다."""
        return f"{self.min_guests}~{self.max_guests}명"

    def contains(self, value: int) -> bool:
        """value 가 [min_guests, max_guests] 안에 포함되는지 검사합니다."""
        return self.min_guests <= value <= self.max_guests


# 모듈 수준 기본 규칙 (하위 호환용 상수도 함께 제공)
DEFAULT_RULE = GuestRule()
MIN_GUESTS: int = DEFAULT_RULE.min_guests   # = 1
MAX_GUESTS: int = DEFAULT_RULE.max_guests   # = 20


# ══════════════════════════════════════════════════════════════════════════════
# 2. 오류 코드
# ══════════════════════════════════════════════════════════════════════════════

class ErrorCode(str, Enum):
    """검증 실패 원인을 세분화하는 코드."""

    INVALID_TYPE  = "INVALID_TYPE"   # int 가 아닌 타입
    BELOW_MINIMUM = "BELOW_MINIMUM"  # 최솟값 미만
    ABOVE_MAXIMUM = "ABOVE_MAXIMUM"  # 최댓값 초과


# ══════════════════════════════════════════════════════════════════════════════
# 3. 커스텀 예외 계층
# ══════════════════════════════════════════════════════════════════════════════

class ReservationError(Exception):
    """예약 관련 기본 예외."""

    def __init__(self, message: str, code: ErrorCode) -> None:
        super().__init__(message)
        self.code: ErrorCode = code


class InvalidGuestTypeError(ReservationError):
    """
    인원 값의 타입이 올바르지 않을 때 발생합니다.

    Attributes
    ----------
    value : Any
        검증에 실패한 원본 입력 값.
    """

    def __init__(self, value: Any) -> None:
        type_name = type(value).__name__
        message = (
            f"인원은 정수(int)여야 합니다. "
            f"입력된 타입: {type_name!r}, 값: {value!r}"
        )
        super().__init__(message, ErrorCode.INVALID_TYPE)
        self.value = value


class GuestCountOutOfRangeError(ReservationError):
    """
    인원이 허용 범위를 벗어났을 때 발생합니다.

    Attributes
    ----------
    value : int
        검증에 실패한 인원 값.
    rule  : GuestRule
        검증에 사용된 규칙 객체.
    """

    def __init__(self, value: int, rule: GuestRule = DEFAULT_RULE) -> None:
        if value < rule.min_guests:
            code   = ErrorCode.BELOW_MINIMUM
            reason = f"최소 인원({rule.min_guests}명)보다 적습니다."
        else:
            code   = ErrorCode.ABOVE_MAXIMUM
            reason = f"최대 인원({rule.max_guests}명)보다 많습니다."

        message = (
            f"인원 {value}명은 허용 범위({rule.range_description})를 벗어났습니다. "
            f"{reason}"
        )
        super().__init__(message, code)
        self.value = value
        self.rule  = rule


# ══════════════════════════════════════════════════════════════════════════════
# 4. 검증 결과 값 객체
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ValidationResult:
    """
    check_guest_count() 의 반환 타입.

    Attributes
    ----------
    is_valid : bool
        검증 통과 여부.
    message : str
        성공 또는 실패 메시지.
    code : ErrorCode | None
        실패 시 오류 코드, 성공 시 None.
    value : int | None
        성공 시 검증된 인원, 실패 시 None.
    """

    is_valid : bool
    message  : str
    code     : ErrorCode | None = field(default=None)
    value    : int | None       = field(default=None)

    def __post_init__(self) -> None:
        # 성공 결과의 내부 일관성 강제
        if self.is_valid:
            if self.value is None:
                raise ValueError("is_valid=True 일 때 value 는 None 일 수 없습니다.")
            if self.code is not None:
                raise ValueError("is_valid=True 일 때 code 는 None 이어야 합니다.")
        else:
            if self.value is not None:
                raise ValueError("is_valid=False 일 때 value 는 None 이어야 합니다.")
            if self.code is None:
                raise ValueError("is_valid=False 일 때 code 는 None 일 수 없습니다.")

    # ── bool 문맥에서 is_valid 처럼 동작 ─────────────────────────────────
    def __bool__(self) -> bool:
        return self.is_valid

    # ── 하위 호환: 튜플처럼 언패킹 지원  (is_valid, message) = result ─────
    def __iter__(self):
        yield self.is_valid
        yield self.message


# ══════════════════════════════════════════════════════════════════════════════
# 5. 핵심 검증 함수
# ══════════════════════════════════════════════════════════════════════════════

def validate_guest_count(guests: Any, rule: GuestRule = DEFAULT_RULE) -> int:
    """
    예약 인원(guests)을 검증한 뒤 유효한 인원(int)을 반환합니다.

    검증 순서
    ---------
    1. 타입 검사   : bool → 먼저 차단, 그 외 비-int → INVALID_TYPE
    2. 경계값 검사 : guests < min_guests → BELOW_MINIMUM
                   guests > max_guests → ABOVE_MAXIMUM

    Parameters
    ----------
    guests : Any
        검증할 예약 인원 값.
    rule : GuestRule
        검증에 사용할 규칙 객체 (기본: DEFAULT_RULE).

    Returns
    -------
    int
        유효성 검사를 통과한 예약 인원.

    Raises
    ------
    InvalidGuestTypeError
        guests 가 순수 int 타입이 아닌 경우.
        (bool 은 int 의 서브클래스이므로 명시적으로 거부합니다.)
    GuestCountOutOfRangeError
        guests 가 rule.min_guests 미만이거나 rule.max_guests 초과인 경우.

    Examples
    --------
    >>> validate_guest_count(1)       # 경계값 최솟값
    1
    >>> validate_guest_count(20)      # 경계값 최댓값
    20
    >>> validate_guest_count(10)      # 중간값
    10
    >>> validate_guest_count(0)       # 최솟값 바로 아래
    Traceback (most recent call last):
        ...
    GuestCountOutOfRangeError: ...
    >>> validate_guest_count(21)      # 최댓값 바로 위
    Traceback (most recent call last):
        ...
    GuestCountOutOfRangeError: ...
    >>> validate_guest_count("5")     # 숫자 문자열 → 거부
    Traceback (most recent call last):
        ...
    InvalidGuestTypeError: ...
    >>> validate_guest_count(True)    # bool → 거부
    Traceback (most recent call last):
        ...
    InvalidGuestTypeError: ...
    """
    # ── 1단계: 타입 검사 ─────────────────────────────────────────────────
    # bool 은 int 의 하위 클래스이므로 isinstance(True, int) == True 입니다.
    # 예약 인원으로 True/False 를 허용하지 않으려면 bool 을 먼저 차단합니다.
    if isinstance(guests, bool) or not isinstance(guests, int):
        raise InvalidGuestTypeError(guests)

    # ── 2단계: 경계값 포함 범위 검사 ─────────────────────────────────────
    # 시스템 극단값(±sys.maxsize) 도 int 이므로 여기서 정상 처리됩니다.
    if not rule.contains(guests):
        raise GuestCountOutOfRangeError(guests, rule)

    return guests


# ══════════════════════════════════════════════════════════════════════════════
# 6. 예외 없는 래퍼 함수
# ══════════════════════════════════════════════════════════════════════════════

def check_guest_count(
    guests: Any,
    rule: GuestRule = DEFAULT_RULE,
) -> ValidationResult:
    """
    validate_guest_count() 를 호출하되, 예외 대신 ValidationResult 를 반환합니다.

    Parameters
    ----------
    guests : Any
        검증할 예약 인원 값.
    rule : GuestRule
        검증에 사용할 규칙 객체 (기본: DEFAULT_RULE).

    Returns
    -------
    ValidationResult
        is_valid=True  → 검증 통과, value 에 인원 수 저장
        is_valid=False → 검증 실패, code 에 ErrorCode 저장

    Notes
    -----
    하위 호환을 위해 튜플 언패킹도 지원합니다::

        is_valid, message = check_guest_count(5)

    Examples
    --------
    >>> result = check_guest_count(5)
    >>> result.is_valid, result.value
    (True, 5)

    >>> result = check_guest_count(0)
    >>> result.is_valid, result.code
    (False, <ErrorCode.BELOW_MINIMUM: 'BELOW_MINIMUM'>)

    >>> result = check_guest_count("five")
    >>> result.is_valid, result.code
    (False, <ErrorCode.INVALID_TYPE: 'INVALID_TYPE'>)
    """
    try:
        validated = validate_guest_count(guests, rule)
        return ValidationResult(
            is_valid = True,
            message  = f"유효한 인원입니다: {validated}명",
            code     = None,
            value    = validated,
        )
    except ReservationError as exc:
        return ValidationResult(
            is_valid = False,
            message  = str(exc),
            code     = exc.code,
            value    = None,
        )
