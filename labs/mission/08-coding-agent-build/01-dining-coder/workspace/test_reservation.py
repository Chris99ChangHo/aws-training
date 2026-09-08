"""
test_reservation.py
===================
reservation.py 의 모든 공개 API 에 대한 pytest 테스트 모음.

테스트 분류
-----------
- 정상 케이스 (valid)
- 경계값 케이스 (boundary)
- 잘못된 입력 (invalid_type / out_of_range)
- GuestRule 생성 검증
- ValidationResult 내부 일관성 검증
- check_guest_count 래퍼
"""

import sys
import pytest

from reservation import (
    GuestRule,
    DEFAULT_RULE,
    MIN_GUESTS,
    MAX_GUESTS,
    ErrorCode,
    InvalidGuestTypeError,
    GuestCountOutOfRangeError,
    ValidationResult,
    validate_guest_count,
    check_guest_count,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. 모듈 수준 상수 기본값 확인
# ══════════════════════════════════════════════════════════════════════════════

class TestModuleConstants:
    def test_min_guests_default(self):
        assert MIN_GUESTS == 1

    def test_max_guests_default(self):
        assert MAX_GUESTS == 20

    def test_default_rule_min(self):
        assert DEFAULT_RULE.min_guests == 1

    def test_default_rule_max(self):
        assert DEFAULT_RULE.max_guests == 20

    def test_range_description(self):
        assert DEFAULT_RULE.range_description == "1~20명"

    def test_contains_min(self):
        assert DEFAULT_RULE.contains(1) is True

    def test_contains_max(self):
        assert DEFAULT_RULE.contains(20) is True

    def test_contains_mid(self):
        assert DEFAULT_RULE.contains(10) is True

    def test_not_contains_below(self):
        assert DEFAULT_RULE.contains(0) is False

    def test_not_contains_above(self):
        assert DEFAULT_RULE.contains(21) is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. GuestRule 생성 검증
# ══════════════════════════════════════════════════════════════════════════════

class TestGuestRule:
    # ── 정상 생성 ────────────────────────────────────────────────────────────
    def test_create_default(self):
        rule = GuestRule()
        assert rule.min_guests == 1
        assert rule.max_guests == 20

    def test_create_custom(self):
        rule = GuestRule(min_guests=2, max_guests=10)
        assert rule.min_guests == 2
        assert rule.max_guests == 10

    def test_create_min_equals_max(self):
        """min == max 는 허용 (1인 전용 룸 등)."""
        rule = GuestRule(min_guests=5, max_guests=5)
        assert rule.min_guests == 5
        assert rule.max_guests == 5

    def test_create_min_is_1(self):
        rule = GuestRule(min_guests=1, max_guests=1)
        assert rule.min_guests == 1

    # ── 타입 오류 ─────────────────────────────────────────────────────────────
    def test_min_guests_float_raises_typeerror(self):
        with pytest.raises(TypeError):
            GuestRule(min_guests=1.0, max_guests=20)

    def test_max_guests_float_raises_typeerror(self):
        with pytest.raises(TypeError):
            GuestRule(min_guests=1, max_guests=20.0)

    def test_min_guests_bool_raises_typeerror(self):
        with pytest.raises(TypeError):
            GuestRule(min_guests=True, max_guests=20)

    def test_max_guests_bool_raises_typeerror(self):
        with pytest.raises(TypeError):
            GuestRule(min_guests=1, max_guests=True)

    def test_min_guests_string_raises_typeerror(self):
        with pytest.raises(TypeError):
            GuestRule(min_guests="1", max_guests=20)

    def test_min_guests_none_raises_typeerror(self):
        with pytest.raises(TypeError):
            GuestRule(min_guests=None, max_guests=20)

    # ── 값 범위 오류 ──────────────────────────────────────────────────────────
    def test_min_guests_zero_raises_valueerror(self):
        with pytest.raises(ValueError, match="min_guests 는 1 이상"):
            GuestRule(min_guests=0, max_guests=20)

    def test_min_guests_negative_raises_valueerror(self):
        with pytest.raises(ValueError, match="min_guests 는 1 이상"):
            GuestRule(min_guests=-1, max_guests=20)

    def test_max_less_than_min_raises_valueerror(self):
        with pytest.raises(ValueError, match="max_guests"):
            GuestRule(min_guests=10, max_guests=5)

    # ── frozen 불변 확인 ──────────────────────────────────────────────────────
    def test_frozen_immutable(self):
        rule = GuestRule()
        with pytest.raises((AttributeError, TypeError)):
            rule.min_guests = 5  # type: ignore[misc]

    # ── range_description / contains ─────────────────────────────────────────
    def test_range_description_custom(self):
        rule = GuestRule(min_guests=3, max_guests=8)
        assert rule.range_description == "3~8명"

    def test_contains_boundary_min(self):
        rule = GuestRule(min_guests=3, max_guests=8)
        assert rule.contains(3) is True

    def test_contains_boundary_max(self):
        rule = GuestRule(min_guests=3, max_guests=8)
        assert rule.contains(8) is True

    def test_not_contains_just_below_min(self):
        rule = GuestRule(min_guests=3, max_guests=8)
        assert rule.contains(2) is False

    def test_not_contains_just_above_max(self):
        rule = GuestRule(min_guests=3, max_guests=8)
        assert rule.contains(9) is False


# ══════════════════════════════════════════════════════════════════════════════
# 3. validate_guest_count — 정상 케이스
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateGuestCountValid:
    def test_returns_int(self):
        assert isinstance(validate_guest_count(5), int)

    def test_value_is_returned_as_is(self):
        assert validate_guest_count(5) == 5

    def test_min_boundary(self):
        """경계값: 최솟값 1."""
        assert validate_guest_count(1) == 1

    def test_max_boundary(self):
        """경계값: 최댓값 20."""
        assert validate_guest_count(20) == 20

    def test_mid_value(self):
        assert validate_guest_count(10) == 10

    def test_min_plus_one(self):
        """경계값 바로 위: 2."""
        assert validate_guest_count(2) == 2

    def test_max_minus_one(self):
        """경계값 바로 아래: 19."""
        assert validate_guest_count(19) == 19

    def test_custom_rule_valid(self):
        rule = GuestRule(min_guests=5, max_guests=50)
        assert validate_guest_count(25, rule) == 25

    def test_custom_rule_min_boundary(self):
        rule = GuestRule(min_guests=5, max_guests=50)
        assert validate_guest_count(5, rule) == 5

    def test_custom_rule_max_boundary(self):
        rule = GuestRule(min_guests=5, max_guests=50)
        assert validate_guest_count(50, rule) == 50


# ══════════════════════════════════════════════════════════════════════════════
# 4. validate_guest_count — 범위 초과 (GuestCountOutOfRangeError)
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateGuestCountOutOfRange:
    # ── 최솟값 미만 ───────────────────────────────────────────────────────────
    def test_zero_raises(self):
        """경계값 바로 아래: 0."""
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(0)

    def test_negative_raises(self):
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(-1)

    def test_large_negative_raises(self):
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(-100)

    def test_sys_neg_maxsize_raises(self):
        """시스템 극단값: -sys.maxsize."""
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(-sys.maxsize)

    def test_below_minimum_error_code(self):
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 0)
        assert exc.value.code == ErrorCode.BELOW_MINIMUM

    def test_below_minimum_error_value(self):
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 0)
        assert exc.value.value == 0

    def test_below_minimum_error_rule(self):
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 0)
        assert exc.value.rule == DEFAULT_RULE

    # ── 최댓값 초과 ───────────────────────────────────────────────────────────
    def test_twenty_one_raises(self):
        """경계값 바로 위: 21."""
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(21)

    def test_large_positive_raises(self):
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(1000)

    def test_sys_maxsize_raises(self):
        """시스템 극단값: sys.maxsize."""
        with pytest.raises(GuestCountOutOfRangeError):
            validate_guest_count(sys.maxsize)

    def test_above_maximum_error_code(self):
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 21)
        assert exc.value.code == ErrorCode.ABOVE_MAXIMUM

    def test_above_maximum_error_value(self):
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 21)
        assert exc.value.value == 21

    def test_above_maximum_error_rule(self):
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 21)
        assert exc.value.rule == DEFAULT_RULE

    # ── 커스텀 룰에서의 범위 초과 ────────────────────────────────────────────
    def test_custom_rule_below(self):
        rule = GuestRule(min_guests=5, max_guests=10)
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 4, rule)
        assert exc.value.code == ErrorCode.BELOW_MINIMUM

    def test_custom_rule_above(self):
        rule = GuestRule(min_guests=5, max_guests=10)
        exc = pytest.raises(GuestCountOutOfRangeError, validate_guest_count, 11, rule)
        assert exc.value.code == ErrorCode.ABOVE_MAXIMUM

    # ── 예외 메시지에 범위 포함 여부 ─────────────────────────────────────────
    def test_error_message_contains_range(self):
        with pytest.raises(GuestCountOutOfRangeError) as exc_info:
            validate_guest_count(0)
        assert "1~20명" in str(exc_info.value)

    def test_error_message_contains_value(self):
        with pytest.raises(GuestCountOutOfRangeError) as exc_info:
            validate_guest_count(99)
        assert "99" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════════════════════
# 5. validate_guest_count — 잘못된 타입 (InvalidGuestTypeError)
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateGuestCountInvalidType:
    # ── bool ─────────────────────────────────────────────────────────────────
    def test_true_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count(True)

    def test_false_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count(False)

    def test_bool_error_code(self):
        exc = pytest.raises(InvalidGuestTypeError, validate_guest_count, True)
        assert exc.value.code == ErrorCode.INVALID_TYPE

    def test_bool_error_value(self):
        exc = pytest.raises(InvalidGuestTypeError, validate_guest_count, True)
        assert exc.value.value is True

    # ── float ─────────────────────────────────────────────────────────────────
    def test_float_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count(5.0)

    def test_float_negative_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count(-1.5)

    # ── str ───────────────────────────────────────────────────────────────────
    def test_numeric_string_raises(self):
        """숫자처럼 생긴 문자열도 자동 변환 없이 거부."""
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count("5")

    def test_alpha_string_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count("five")

    def test_empty_string_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count("")

    # ── None ─────────────────────────────────────────────────────────────────
    def test_none_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count(None)

    def test_none_error_code(self):
        exc = pytest.raises(InvalidGuestTypeError, validate_guest_count, None)
        assert exc.value.code == ErrorCode.INVALID_TYPE

    # ── list / dict / tuple ──────────────────────────────────────────────────
    def test_list_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count([5])

    def test_dict_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count({"guests": 5})

    def test_tuple_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count((5,))

    # ── complex ──────────────────────────────────────────────────────────────
    def test_complex_raises(self):
        with pytest.raises(InvalidGuestTypeError):
            validate_guest_count(5 + 0j)

    # ── 예외 메시지에 타입명 포함 여부 ───────────────────────────────────────
    def test_error_message_contains_type_name(self):
        with pytest.raises(InvalidGuestTypeError) as exc_info:
            validate_guest_count("5")
        assert "str" in str(exc_info.value)

    def test_error_message_contains_value(self):
        with pytest.raises(InvalidGuestTypeError) as exc_info:
            validate_guest_count(None)
        assert "None" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════════════════════
# 6. check_guest_count — 정상 케이스
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckGuestCountValid:
    def test_returns_validation_result(self):
        result = check_guest_count(5)
        assert isinstance(result, ValidationResult)

    def test_is_valid_true(self):
        assert check_guest_count(5).is_valid is True

    def test_value_stored(self):
        assert check_guest_count(5).value == 5

    def test_code_is_none_on_success(self):
        assert check_guest_count(5).code is None

    def test_message_not_empty(self):
        assert check_guest_count(5).message != ""

    def test_message_contains_value(self):
        assert "5" in check_guest_count(5).message

    def test_min_boundary(self):
        result = check_guest_count(1)
        assert result.is_valid and result.value == 1

    def test_max_boundary(self):
        result = check_guest_count(20)
        assert result.is_valid and result.value == 20

    def test_bool_context_true(self):
        """ValidationResult 의 __bool__ 이 is_valid 를 반환해야 함."""
        assert bool(check_guest_count(10)) is True

    def test_tuple_unpack(self):
        """하위 호환 튜플 언패킹: (is_valid, message)."""
        is_valid, message = check_guest_count(10)
        assert is_valid is True
        assert isinstance(message, str)

    def test_custom_rule_valid(self):
        rule = GuestRule(min_guests=2, max_guests=5)
        result = check_guest_count(3, rule)
        assert result.is_valid and result.value == 3


# ══════════════════════════════════════════════════════════════════════════════
# 7. check_guest_count — 실패 케이스 (예외 없는 래퍼)
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckGuestCountInvalid:
    # ── 범위 미만 ─────────────────────────────────────────────────────────────
    def test_zero_is_invalid(self):
        assert check_guest_count(0).is_valid is False

    def test_zero_code(self):
        assert check_guest_count(0).code == ErrorCode.BELOW_MINIMUM

    def test_zero_value_is_none(self):
        assert check_guest_count(0).value is None

    def test_negative_is_invalid(self):
        assert check_guest_count(-5).is_valid is False

    def test_negative_code(self):
        assert check_guest_count(-5).code == ErrorCode.BELOW_MINIMUM

    def test_sys_neg_maxsize_code(self):
        assert check_guest_count(-sys.maxsize).code == ErrorCode.BELOW_MINIMUM

    # ── 범위 초과 ─────────────────────────────────────────────────────────────
    def test_twenty_one_is_invalid(self):
        assert check_guest_count(21).is_valid is False

    def test_twenty_one_code(self):
        assert check_guest_count(21).code == ErrorCode.ABOVE_MAXIMUM

    def test_large_number_code(self):
        assert check_guest_count(sys.maxsize).code == ErrorCode.ABOVE_MAXIMUM

    # ── 잘못된 타입 ───────────────────────────────────────────────────────────
    def test_bool_is_invalid(self):
        assert check_guest_count(True).is_valid is False

    def test_bool_code(self):
        assert check_guest_count(True).code == ErrorCode.INVALID_TYPE

    def test_none_is_invalid(self):
        assert check_guest_count(None).is_valid is False

    def test_none_code(self):
        assert check_guest_count(None).code == ErrorCode.INVALID_TYPE

    def test_string_is_invalid(self):
        assert check_guest_count("5").is_valid is False

    def test_string_code(self):
        assert check_guest_count("5").code == ErrorCode.INVALID_TYPE

    def test_float_is_invalid(self):
        assert check_guest_count(5.0).is_valid is False

    def test_float_code(self):
        assert check_guest_count(5.0).code == ErrorCode.INVALID_TYPE

    def test_list_is_invalid(self):
        assert check_guest_count([5]).is_valid is False

    # ── bool 문맥에서 False ───────────────────────────────────────────────────
    def test_bool_context_false(self):
        assert bool(check_guest_count(0)) is False

    # ── 튜플 언패킹 실패 케이스 ───────────────────────────────────────────────
    def test_tuple_unpack_invalid(self):
        is_valid, message = check_guest_count(0)
        assert is_valid is False
        assert isinstance(message, str)

    # ── 메시지 비어 있지 않음 ──────────────────────────────────────────────────
    def test_message_not_empty_on_failure(self):
        assert check_guest_count(0).message != ""

    # ── 커스텀 룰 실패 ────────────────────────────────────────────────────────
    def test_custom_rule_below(self):
        rule = GuestRule(min_guests=5, max_guests=10)
        result = check_guest_count(4, rule)
        assert result.is_valid is False
        assert result.code == ErrorCode.BELOW_MINIMUM

    def test_custom_rule_above(self):
        rule = GuestRule(min_guests=5, max_guests=10)
        result = check_guest_count(11, rule)
        assert result.is_valid is False
        assert result.code == ErrorCode.ABOVE_MAXIMUM


# ══════════════════════════════════════════════════════════════════════════════
# 8. ValidationResult — 내부 일관성 강제
# ══════════════════════════════════════════════════════════════════════════════

class TestValidationResult:
    # ── 성공 객체 정상 생성 ───────────────────────────────────────────────────
    def test_valid_result_ok(self):
        r = ValidationResult(is_valid=True, message="ok", code=None, value=5)
        assert r.is_valid and r.value == 5

    # ── is_valid=True 일 때 value=None 은 허용 불가 ──────────────────────────
    def test_valid_result_value_none_raises(self):
        with pytest.raises(ValueError):
            ValidationResult(is_valid=True, message="ok", code=None, value=None)

    # ── is_valid=True 일 때 code != None 은 허용 불가 ────────────────────────
    def test_valid_result_code_not_none_raises(self):
        with pytest.raises(ValueError):
            ValidationResult(
                is_valid=True,
                message="ok",
                code=ErrorCode.INVALID_TYPE,
                value=5,
            )

    # ── 실패 객체 정상 생성 ───────────────────────────────────────────────────
    def test_invalid_result_ok(self):
        r = ValidationResult(
            is_valid=False,
            message="bad",
            code=ErrorCode.INVALID_TYPE,
            value=None,
        )
        assert not r.is_valid and r.code == ErrorCode.INVALID_TYPE

    # ── is_valid=False 일 때 value != None 은 허용 불가 ──────────────────────
    def test_invalid_result_value_not_none_raises(self):
        with pytest.raises(ValueError):
            ValidationResult(
                is_valid=False,
                message="bad",
                code=ErrorCode.INVALID_TYPE,
                value=5,
            )

    # ── is_valid=False 일 때 code=None 은 허용 불가 ──────────────────────────
    def test_invalid_result_code_none_raises(self):
        with pytest.raises(ValueError):
            ValidationResult(is_valid=False, message="bad", code=None, value=None)

    # ── frozen 불변 ──────────────────────────────────────────────────────────
    def test_frozen(self):
        r = ValidationResult(is_valid=True, message="ok", code=None, value=5)
        with pytest.raises((AttributeError, TypeError)):
            r.is_valid = False  # type: ignore[misc]

    # ── __bool__ ─────────────────────────────────────────────────────────────
    def test_bool_true(self):
        r = ValidationResult(is_valid=True, message="ok", code=None, value=5)
        assert bool(r) is True

    def test_bool_false(self):
        r = ValidationResult(
            is_valid=False, message="bad",
            code=ErrorCode.BELOW_MINIMUM, value=None
        )
        assert bool(r) is False

    # ── __iter__ (튜플 언패킹) ────────────────────────────────────────────────
    def test_iter_unpacking(self):
        r = ValidationResult(is_valid=True, message="ok", code=None, value=5)
        is_valid, message = r
        assert is_valid is True
        assert message == "ok"
