# ──────────────────────────────────────────────
#  test_hanwoo.py  –  한우명가 35명 / 25명 검증 테스트
# ──────────────────────────────────────────────
from reservation import validate_reservation

print("=" * 60)
print("  한우명가 예약 인원 검증 테스트")
print("=" * 60)

# ── 테스트 1: 35명 요청 (거절 예상) ──────────────
print("\n[테스트 1]  한우명가 / 35명 요청")
result_35 = validate_reservation("한우명가", 35)
print(f"  available : {result_35['available']}")
print(f"  message   : {result_35['message']}")
assert result_35["available"] is False, "❌ 35명은 거절되어야 합니다!"
print("  ✅ 결과 확인: 35명 요청 → 거절(available=False)  PASS")

# ── 테스트 2: 25명 요청 (통과 예상) ──────────────
print("\n[테스트 2]  한우명가 / 25명 요청")
result_25 = validate_reservation("한우명가", 25)
print(f"  available : {result_25['available']}")
print(f"  message   : {result_25['message']}")
assert result_25["available"] is True, "❌ 25명은 통과되어야 합니다!"
print("  ✅ 결과 확인: 25명 요청 → 통과(available=True)   PASS")

print("\n" + "=" * 60)
print("  모든 테스트 통과!")
print("=" * 60)
