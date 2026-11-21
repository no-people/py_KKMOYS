"""기능 1 ledger.validate 테스트 — 공통모듈_함수규격.md 4-1, 규약 1·3·4·6-2 경계값.

그날 회원 검사는 queries.is_member_active(기능 5)를 부른다.
- TestOk(정상 반환)는 규격 3-6 대로 만든 대역으로 바꿔 끼워 지금도 실행한다.
- TestActive(회원 기간의 뜻)는 실제 구현으로 본다. 아직 구현 전이면(NotImplementedError)
  건너뜀(skipped)으로 나오고, 병합되면 저절로 실행된다.
"""

import datetime as dt
import functools
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import NAMES, StoreCase  # noqa: E402
from moim.common import dates  # noqa: E402
from moim.common.ledger import validate  # noqa: E402

KIM, LEE, PARK = NAMES


def spec_active(store, name, on):
    """공통모듈_함수규격.md 3-6 대역: joined <= on <= left(left 가 None 이면 joined <= on), 명부에 없으면 False."""
    m = store.member(name)
    if m is None:
        return False
    d = dates.parse(on)
    return dates.parse(m["joined"]) <= d and (m["left"] is None or d <= dates.parse(m["left"]))


def needs_active(test):
    """is_member_active 가 아직 구현 전이면 건너뛴다."""
    @functools.wraps(test)
    def wrapper(self):
        try:
            test(self)
        except NotImplementedError as exc:
            self.skipTest(f"아직 구현 전: {exc}")
    return wrapper


class ValidateCase(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.member(PARK)["left"] = "2026-11-15"   # 박지훈: 2026-09-01 가입, 11-15 탈퇴

    def bad(self, *args, reason=None, **kw):
        """ValueError 인지, reason 을 주면 메시지에 그 이유가 들어 있는지까지 본다."""
        with self.assertRaisesRegex(ValueError, reason or ""):
            validate(self.store, *args, **kw)


@mock.patch("moim.common.ledger.is_member_active", spec_active)
class TestOk(ValidateCase):
    def test_basic(self):
        self.assertEqual(validate(self.store, "2026-11-12", KIM, "36,000원", [KIM, LEE]), ("2026-11-12", 36000))

    def test_half_up_payer_not_member_of_expense(self):
        """1234.5 → 1235(사사오입), 낸 사람이 참여자가 아니어도 된다."""
        self.assertEqual(validate(self.store, "2026-11-12", KIM, "1234.5", [LEE]), ("2026-11-12", 1235))

    def test_half_up_boundary(self):
        self.assertEqual(validate(self.store, "2026-11-12", KIM, "0.5", [KIM])[1], 1)
        self.assertEqual(validate(self.store, "2026-11-12", KIM, 2.5, [KIM])[1], 3)

    def test_date_object_returns_string(self):
        self.assertEqual(validate(self.store, dt.date(2026, 11, 12), KIM, 1000, [KIM])[0], "2026-11-12")

    def test_leap_day(self):
        self.assertEqual(validate(self.store, "2028-02-29", KIM, 1000, [KIM])[0], "2028-02-29")

    def test_weights_ok(self):
        self.assertEqual(validate(self.store, "2026-11-12", KIM, 3000, [KIM, LEE], weights={KIM: 2, LEE: 1}),
                         ("2026-11-12", 3000))

    def test_does_not_save_or_change_data(self):
        before = repr(self.store.data)
        validate(self.store, "2026-11-12", KIM, 1000, [KIM])
        self.assertEqual(repr(self.store.data), before)
        self.assertFalse(os.path.exists(self.store.path))

    def test_locked_period_not_checked(self):
        """확정 기간 검사는 insert 몫이다. validate 는 통과시킨다."""
        self.store.data["locks"].append({"start": "2026-11-01", "end": "2026-11-30"})
        self.assertEqual(validate(self.store, "2026-11-30", KIM, 1000, [KIM])[0], "2026-11-30")


class TestAmount(ValidateCase):
    def test_zero_or_negative(self):
        for amount in ("0", 0, -3000, "-1", "0.4"):
            with self.subTest(amount=amount):
                self.bad("2026-11-12", KIM, amount, [KIM], reason="0원 이하")

    def test_bad_format(self):
        for amount in ("abc", "", "Infinity", "NaN", True, None):
            with self.subTest(amount=amount):
                self.bad("2026-11-12", KIM, amount, [KIM])


class TestDate(ValidateCase):
    def test_bad_date(self):
        for day in ("2026-11-31", "2026/11/12", "2026-02-29", "", "20261112"):
            with self.subTest(day=day):
                self.bad(day, KIM, 1000, [KIM])


class TestPeople(ValidateCase):
    def test_no_members(self):
        self.bad("2026-11-12", KIM, 3000, [])

    def test_duplicate_members(self):
        self.bad("2026-11-12", KIM, 3000, [KIM, LEE, KIM])

    def test_member_not_in_roster(self):
        self.bad("2026-11-12", KIM, 3000, ["없는사람"], reason="명부에 없는")
        self.bad("2026-11-12", KIM, 3000, [KIM, "없는사람"], reason="명부에 없는")

    def test_payer_not_in_roster(self):
        self.bad("2026-11-12", "없는사람", 3000, [KIM], reason="명부에 없는")

    def test_payer_empty(self):
        self.bad("2026-11-12", "", 3000, [KIM])
        self.bad("2026-11-12", None, 3000, [KIM])

    def test_members_not_list(self):
        """문자열 하나를 넘기면 글자 목록으로 보지 않고 거부한다."""
        self.bad("2026-11-12", KIM, 3000, KIM)
        self.bad("2026-11-12", KIM, 3000, None)


class TestWeights(ValidateCase):
    def test_missing_member(self):
        self.bad("2026-11-12", KIM, 3000, [KIM, LEE], weights={KIM: 1})

    def test_extra_name(self):
        self.bad("2026-11-12", KIM, 3000, [KIM], weights={KIM: 1, LEE: 1})

    def test_not_positive_int(self):
        for w in (0, -1, 1.5, "2", True):
            with self.subTest(w=w):
                self.bad("2026-11-12", KIM, 3000, [KIM, LEE], weights={KIM: 1, LEE: w})

    def test_not_dict(self):
        self.bad("2026-11-12", KIM, 3000, [KIM], weights=[1])

    def test_payer_not_member_in_weights(self):
        """낸 사람이 참여자가 아니면 weights 에 들어 있어도 안 된다."""
        self.bad("2026-11-12", KIM, 3000, [LEE], weights={KIM: 1, LEE: 1}, reason="참여자와 맞지 않")


class TestActive(ValidateCase):
    """규약 4: 가입일부터 탈퇴일 당일까지 회원. 규약 6-2: 낸 사람도 그날 회원이어야 한다."""

    @needs_active
    def test_left_day_is_member(self):
        self.assertEqual(validate(self.store, "2026-11-15", PARK, 1000, [PARK])[0], "2026-11-15")

    @needs_active
    def test_left_day_payer_only(self):
        """탈퇴일 당일에는 낸 사람(참여자 아님)으로도 통과한다."""
        self.assertEqual(validate(self.store, "2026-11-15", PARK, 1000, [KIM])[0], "2026-11-15")

    @needs_active
    def test_day_after_left_member_rejected(self):
        self.bad("2026-11-16", KIM, 3000, [KIM, PARK], reason="그날 회원이 아닙니다")

    @needs_active
    def test_day_after_left_payer_rejected(self):
        """낸 사람이 참여자가 아니어도 그날 회원이어야 한다."""
        self.bad("2026-11-16", PARK, 3000, [KIM], reason="그날 회원이 아닙니다")

    @needs_active
    def test_joined_day_and_day_before(self):
        self.assertEqual(validate(self.store, "2026-09-01", KIM, 1000, [KIM])[0], "2026-09-01")
        self.bad("2026-08-31", KIM, 1000, [KIM], reason="그날 회원이 아닙니다")


if __name__ == "__main__":
    unittest.main()
