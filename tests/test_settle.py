"""기능 4 정산 테스트. 공통 함수 queries.is_locked 와 자료 항목 locks 포함."""

import datetime as dt
import json

from helpers import StoreCase

from moim.common import money, queries
from moim.common.store import Store


class SplitWeightsTest(StoreCase):
    """money.split 비율 분배. 공통모듈_함수규격.md 1-1, 규약 2."""

    MEMBERS = ["가", "나", "다"]

    def test_spec_example_remainder_to_payer(self):
        # 규격 1-1 예: 101×2//4=50, 25, 25 → 합 100, 남는 1원 → 낸 사람 다
        self.assertEqual(money.split(101, self.MEMBERS, payer="다", weights={"가": 2, "나": 1, "다": 1}),
                         {"가": 50, "나": 25, "다": 26})

    def test_remainder_in_member_order_when_payer_not_member(self):
        # 100×1//6=16, 33, 50 → 합 99, 남는 1원 → 라는 참여자가 아니므로 목록 첫 사람 가
        self.assertEqual(money.split(100, self.MEMBERS, payer="라", weights={"가": 1, "나": 2, "다": 3}),
                         {"가": 17, "나": 33, "다": 50})

    def test_several_remainder_won(self):
        # 10×1//7=1, 10×3//7=4, 10×3//7=4 → 합 9, 남는 1원 → 낸 사람 나
        self.assertEqual(money.split(10, self.MEMBERS, payer="나", weights={"가": 1, "나": 3, "다": 3}),
                         {"가": 1, "나": 5, "다": 4})
        # 5×1//3=1씩 → 합 3, 남는 2원 → 낸 사람 다, 그다음 목록 순서 가
        self.assertEqual(money.split(5, self.MEMBERS, payer="다", weights={"가": 1, "나": 1, "다": 1}),
                         {"가": 2, "나": 1, "다": 2})

    def test_sum_always_amount(self):
        weights = {"가": 3, "나": 5, "다": 7}
        for amount in (0, 1, 2, 14, 15, 16, 9999, 10000, 123457):
            shares = money.split(amount, self.MEMBERS, payer="나", weights=weights)
            self.assertEqual(sum(shares.values()), amount, amount)

    def test_zero_amount(self):
        self.assertEqual(money.split(0, self.MEMBERS, weights={"가": 2, "나": 1, "다": 1}),
                         {"가": 0, "나": 0, "다": 0})

    def test_keys_in_member_order(self):
        shares = money.split(100, ["다", "가", "나"], weights={"가": 1, "나": 1, "다": 2})
        self.assertEqual(list(shares), ["다", "가", "나"])

    def test_equal_weights_same_as_none(self):
        self.assertEqual(money.split(100, self.MEMBERS, payer="나", weights={"가": 1, "나": 1, "다": 1}),
                         money.split(100, self.MEMBERS, payer="나"))

    def test_extra_name_in_weights_ignored(self):
        # 참여자가 아닌 이름의 비율은 쓰지 않는다(참여자와 맞는지는 ledger.validate 가 검사)
        self.assertEqual(money.split(100, ["가", "나"], weights={"가": 1, "나": 1, "다": 5}),
                         {"가": 50, "나": 50})

    def test_missing_member_weight_raises(self):
        with self.assertRaises(ValueError):
            money.split(100, self.MEMBERS, weights={"가": 1, "나": 1})

    def test_empty_weights_raises(self):
        # {} 는 None(균등)이 아니라 "참여자의 비율이 없음"
        with self.assertRaises(ValueError):
            money.split(100, self.MEMBERS, weights={})

    def test_zero_or_negative_weight_raises(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                money.split(100, self.MEMBERS, weights={"가": 1, "나": bad, "다": 1})

    def test_non_dict_weights_raises(self):
        # 손으로 고친 자료의 "weights": [1, 2] 같은 값도 AttributeError 가 아니라 ValueError (ledger.validate 와 같음)
        for bad in ([1, 1, 1], (1, 1, 1), "가:1", 1):
            with self.assertRaises(ValueError):
                money.split(100, self.MEMBERS, weights=bad)

    def test_non_int_weight_raises(self):
        for bad in (1.5, "2", True, None):
            with self.assertRaises(ValueError):
                money.split(100, self.MEMBERS, weights={"가": 1, "나": bad, "다": 1})

    def test_non_int_amount_raises(self):
        # 규격 1-1 amount: int. 소수·bool·문자열은 ValueError (True 가 1원으로 계산되지 않게)
        for bad in (100.0, True, "100", None):
            with self.assertRaises(ValueError):
                money.split(bad, self.MEMBERS)
            with self.assertRaises(ValueError):
                money.split(bad, self.MEMBERS, weights={"가": 1, "나": 1, "다": 1})

    def test_members_not_list_raises(self):
        # 문자열 "가나" 를 글자별 참여자로 나누지 않는다
        with self.assertRaises(ValueError):
            money.split(100, "가나")

    def test_duplicate_members_raises(self):
        with self.assertRaises(ValueError):
            money.split(100, ["가", "가"])

    def test_tuple_members_ok(self):
        self.assertEqual(money.split(100, ("가", "나"), weights={"가": 3, "나": 1}), {"가": 75, "나": 25})

    def test_error_message_shows_type(self):
        # 문자 "2" 와 숫자 2 를 메시지에서 구분한다
        with self.assertRaises(ValueError) as cm:
            money.split(100, self.MEMBERS, weights={"가": 1, "나": "2", "다": 1})
        self.assertIn("'2'", str(cm.exception))


class IsLockedTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["locks"].append({"start": "2026-11-01", "end": "2026-11-30"})

    def test_empty_has_locks(self):
        self.assertEqual(Store(self.path("new.json")).load().data["locks"], [])

    def test_no_locks_is_false(self):
        self.store.data["locks"] = []
        self.assertFalse(queries.is_locked(self.store, "2026-11-15"))

    def test_start_and_end_included(self):
        # 규약 6: 확정 기간의 시작일·끝일도 잠긴다
        self.assertTrue(queries.is_locked(self.store, "2026-11-01"))
        self.assertTrue(queries.is_locked(self.store, "2026-11-30"))

    def test_outside_period(self):
        self.assertFalse(queries.is_locked(self.store, "2026-10-31"))
        self.assertFalse(queries.is_locked(self.store, "2026-12-01"))

    def test_any_of_several_locks(self):
        self.store.data["locks"].append({"start": "2027-01-01", "end": "2027-01-31"})
        self.assertTrue(queries.is_locked(self.store, "2027-01-31"))
        self.assertFalse(queries.is_locked(self.store, "2026-12-15"))

    def test_old_file_without_locks(self):
        # locks 가 없는 옛 자료 파일도 읽으면 기본값 [] 로 채워져 False
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1}, f)
        old = Store(self.path("old.json")).load()
        self.assertFalse(queries.is_locked(old, "2026-11-15"))

    def test_old_file_locks_null(self):
        # "locks": null 인 옛 자료 파일도 TypeError 없이 False (규격 3-10 "locks 가 없으면 False")
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1, "locks": None}, f)
        old = Store(self.path("old.json")).load()
        self.assertFalse(queries.is_locked(old, "2026-11-15"))

    def test_locks_not_list_raises(self):
        # 깨진 locks 를 확정 기간 없음으로 넘기지 않는다
        for bad in ({}, "abc", 0, False):
            self.store.data["locks"] = bad
            with self.assertRaisesRegex(ValueError, "locks 형식"):
                queries.is_locked(self.store, "2026-11-15")

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            queries.is_locked(self.store, "2026-11-31")

    def test_bad_date_raises_without_locks(self):
        # 확정 기간이 비어 있어도 없는 날짜·형식이 틀린 날짜는 False 가 아니라 ValueError
        self.store.data["locks"] = []
        for bad in ("2026-11-31", "2026-02-29", "2026/11/15", "", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    queries.is_locked(self.store, bad)

    def test_bad_date_raises_with_locks_null(self):
        self.store.data["locks"] = None
        with self.assertRaises(ValueError):
            queries.is_locked(self.store, "2026-11-31")

    def test_leap_day_valid_without_locks(self):
        # 윤년 2028-02-29 는 있는 날짜이므로 확정 기간이 없으면 오류 없이 False
        self.store.data["locks"] = []
        self.assertFalse(queries.is_locked(self.store, "2028-02-29"))

    def test_date_object_accepted(self):
        self.assertTrue(queries.is_locked(self.store, dt.date(2026, 11, 30)))
        self.assertFalse(queries.is_locked(self.store, dt.date(2026, 12, 1)))


class WeightsFormatTest(StoreCase):
    """지출 한 건의 weights 항목: {참여자 전원의 이름: 1 이상 정수 비율} 또는 None(균등). 공통모듈_함수규격.md "지출 한 건의 형식"."""

    def _expense(self, eid, weights="없음"):
        e = {"id": eid, "date": "2026-11-12", "payer": "김민수", "amount": 101,
             "members": ["김민수", "이서연", "박지훈"], "category": None, "memo": ""}
        if weights != "없음":
            e["weights"] = weights
        return e

    def test_weights_saved_and_loaded_as_int_dict(self):
        self.store.data["expenses"].append(self._expense(1, {"김민수": 2, "이서연": 1, "박지훈": 1}))
        self.store.save()
        e = Store(self.store.path).load().get_expense(1)
        self.assertEqual(e["weights"], {"김민수": 2, "이서연": 1, "박지훈": 1})
        self.assertTrue(all(type(w) is int for w in e["weights"].values()))

    def test_none_weights_kept_as_none(self):
        self.store.data["expenses"].append(self._expense(1, None))
        self.store.save()
        self.assertIsNone(Store(self.store.path).load().get_expense(1)["weights"])

    def test_old_expense_without_weights_reads_as_none(self):
        # weights 가 생기기 전의 옛 자료 파일: 읽는 쪽은 e.get("weights") 로 None(균등)을 얻는다
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [self._expense(1)], "next_id": 2}, f)
        e = Store(self.path("old.json")).load().get_expense(1)
        self.assertNotIn("weights", e)
        self.assertIsNone(e.get("weights"))


class RecurringFormatTest(StoreCase):
    """자료 항목 recurring. 공통모듈_함수규격.md "EMPTY 에 새로 추가할 최상위 항목" 표의 recurring 행."""

    R = {"id": 1, "day": 31, "payer": "김민수", "amount": 300000, "members": ["김민수", "이서연", "박지훈"],
         "memo": "정기 대관료", "category": None, "start": "2026-11", "made": ["2026-11"]}

    def test_empty_has_recurring(self):
        self.assertEqual(Store(self.path("new.json")).load().data["recurring"], [])

    def test_saved_and_loaded(self):
        self.store.data["recurring"].append(dict(self.R))
        self.store.save()
        loaded = Store(self.store.path).load().data["recurring"]
        self.assertEqual(loaded, [self.R])
        self.assertIs(type(loaded[0]["day"]), int)
        self.assertIs(type(loaded[0]["amount"]), int)
        self.assertEqual(loaded[0]["made"], ["2026-11"])
        self.assertEqual(loaded[0]["start"], "2026-11")
        self.assertIsNone(loaded[0]["category"])   # add_recurring 은 분류를 받지 않으므로 None(미분류)

    def test_old_file_without_recurring(self):
        # recurring 이 생기기 전의 옛 자료 파일도 읽으면 기본값 [] 로 채워진다
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1}, f)
        self.assertEqual(Store(self.path("old.json")).load().data["recurring"], [])

    def test_existing_recurring_kept_on_load(self):
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 2, "recurring": [self.R]}, f)
        self.assertEqual(Store(self.path("old.json")).load().data["recurring"], [self.R])


class ExpenseSharesTest(StoreCase):
    """queries.expense_shares. 공통모듈_함수규격.md 3-8, 규약 2."""

    def _e(self, **kw):
        e = {"id": 1, "date": "2026-11-12", "payer": "이서연", "amount": 100,
             "members": ["김민수", "이서연", "박지훈"], "weights": None, "category": None,
             "memo": "", "deleted": False, "recurring_id": None}
        e.update(kw)
        return e

    def test_spec_example(self):
        # 규격 3-8 예: 100원, 낸 사람 이서연 → 남는 1원은 이서연
        self.assertEqual(queries.expense_shares(self._e()), {"김민수": 33, "이서연": 34, "박지훈": 33})

    def test_weights_used(self):
        e = self._e(amount=101, payer="박지훈", weights={"김민수": 2, "이서연": 1, "박지훈": 1})
        self.assertEqual(queries.expense_shares(e), {"김민수": 50, "이서연": 25, "박지훈": 26})

    def test_same_as_money_split(self):
        # 따로 나누지 않고 money.split 결과와 같다
        e = self._e(amount=10000, payer="라", weights={"김민수": 3, "이서연": 5, "박지훈": 7})
        self.assertEqual(queries.expense_shares(e),
                         money.split(10000, e["members"], "라", e["weights"]))

    def test_old_expense_without_weights_key(self):
        # weights 키가 없는 옛 지출은 균등
        e = self._e()
        del e["weights"]
        self.assertEqual(queries.expense_shares(e), {"김민수": 33, "이서연": 34, "박지훈": 33})

    def test_payer_not_member(self):
        e = self._e(amount=101, payer="외부인")
        self.assertEqual(queries.expense_shares(e), {"김민수": 34, "이서연": 34, "박지훈": 33})

    def test_sum_equals_amount(self):
        e = self._e(amount=36001, weights={"김민수": 1, "이서연": 2, "박지훈": 4})
        self.assertEqual(sum(queries.expense_shares(e).values()), 36001)

    def test_does_not_change_expense(self):
        e = self._e(weights={"김민수": 2, "이서연": 1, "박지훈": 1})
        before = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                  for k, v in e.items()}
        queries.expense_shares(e)
        self.assertEqual(e, before)

    def test_bad_weights_raise(self):
        with self.assertRaises(ValueError):
            queries.expense_shares(self._e(weights={"김민수": 1}))

    def test_zero_amount(self):
        self.assertEqual(queries.expense_shares(self._e(amount=0)), {"김민수": 0, "이서연": 0, "박지훈": 0})

    def test_negative_amount_raises(self):
        with self.assertRaises(ValueError):
            queries.expense_shares(self._e(amount=-1))

    def test_single_member_payer_outside(self):
        # 참여자 1명, 낸 사람은 참여자가 아님 → 그 한 명이 전액
        self.assertEqual(queries.expense_shares(self._e(amount=5, payer="김민수", members=["박지훈"])),
                         {"박지훈": 5})


class MemberSharesTest(StoreCase):
    """queries.member_shares. 공통모듈_함수규격.md 3-9, 규약 2·3·6-1."""

    S, E = "2026-11-10", "2026-11-20"

    def _add(self, date, payer, amount, members=None, weights=None, deleted=False):
        e = {"id": self.store.new_id(), "date": date, "payer": payer, "amount": amount,
             "members": members or ["김민수", "이서연", "박지훈"], "weights": weights,
             "category": None, "memo": "", "deleted": deleted, "recurring_id": None}
        self.store.data["expenses"].append(e)
        return e

    def test_spec_example(self):
        # 규격 3-9 예: 11-12 이서연 6,000 → 2000씩, 11-13 김민수 100 더 → 나머지 1원은 김민수
        self._add("2026-11-12", "이서연", 6000)
        self.assertEqual(queries.member_shares(self.store, self.S, self.E),
                         {"김민수": 2000, "이서연": 2000, "박지훈": 2000})
        self._add("2026-11-13", "김민수", 100)
        self.assertEqual(queries.member_shares(self.store, self.S, self.E),
                         {"김민수": 2034, "이서연": 2033, "박지훈": 2033})

    def test_period_start_end_included(self):
        # 규약 3: 시작일·끝일 포함, 밖은 제외
        self._add("2026-11-09", "김민수", 3000)
        self._add("2026-11-10", "김민수", 300)
        self._add("2026-11-20", "김민수", 600)
        self._add("2026-11-21", "김민수", 9000)
        self.assertEqual(queries.member_shares(self.store, self.S, self.E),
                         {"김민수": 300, "이서연": 300, "박지훈": 300})

    def test_deleted_excluded(self):
        # 규약 6-1: 삭제 표시한 지출은 정산에서 뺀다
        self._add("2026-11-12", "김민수", 3000)
        self._add("2026-11-13", "김민수", 9000, deleted=True)
        self.assertEqual(queries.member_shares(self.store, self.S, self.E),
                         {"김민수": 1000, "이서연": 1000, "박지훈": 1000})

    def test_sum_equals_period_total(self):
        # 합계는 기간 안(삭제 제외) 지출 금액 합(= period_total)과 같다
        self._add("2026-11-12", "김민수", 10001, weights={"김민수": 1, "이서연": 2, "박지훈": 4})
        self._add("2026-11-13", "이서연", 333, members=["이서연", "박지훈"])
        self._add("2026-11-14", "박지훈", 7)
        self._add("2026-11-15", "박지훈", 5000, deleted=True)
        shares = queries.member_shares(self.store, self.S, self.E)
        self.assertEqual(sum(shares.values()), 10001 + 333 + 7)

    def test_weights_and_partial_members(self):
        self._add("2026-11-12", "박지훈", 101, weights={"김민수": 2, "이서연": 1, "박지훈": 1})
        self._add("2026-11-13", "이서연", 1001, members=["이서연", "박지훈"])
        self.assertEqual(queries.member_shares(self.store, self.S, self.E),
                         {"김민수": 50, "이서연": 25 + 501, "박지훈": 26 + 500})

    def test_only_people_who_owe(self):
        # 그 기간 지출에 참여하지 않은 사람은 결과에 없다
        self._add("2026-11-12", "김민수", 1000, members=["김민수", "이서연"])
        self.assertEqual(queries.member_shares(self.store, self.S, self.E), {"김민수": 500, "이서연": 500})

    def test_empty_period(self):
        self._add("2026-12-01", "김민수", 3000)
        self.assertEqual(queries.member_shares(self.store, self.S, self.E), {})

    def test_old_expense_without_weights_or_deleted(self):
        # weights·deleted 키가 없는 옛 지출도 균등·삭제 아님으로 본다
        self.store.data["expenses"].append({"id": 1, "date": "2026-11-12", "payer": "김민수",
                                            "amount": 3000, "members": ["김민수", "이서연", "박지훈"],
                                            "category": None, "memo": ""})
        self.assertEqual(queries.member_shares(self.store, self.S, self.E),
                         {"김민수": 1000, "이서연": 1000, "박지훈": 1000})

    def test_broken_expense_error_has_id(self):
        # 나눌 수 없는 지출은 번호가 담긴 ValueError (KeyError 가 그대로 올라가지 않음)
        e = self._add("2026-11-12", "김민수", 1000, weights={"김민수": 1})
        with self.assertRaisesRegex(ValueError, f"{e['id']}번 지출"):
            queries.member_shares(self.store, self.S, self.E)
        self.store.data["expenses"] = [{"id": 7, "date": "2026-11-12", "amount": 1000,
                                        "members": ["김민수"]}]   # payer 없음
        with self.assertRaisesRegex(ValueError, "7번 지출"):
            queries.member_shares(self.store, self.S, self.E)
        self.store.data["expenses"] = [{"id": 8, "date": "2026-11-12", "payer": "김민수", "amount": 1000,
                                        "members": [["김민수"]]}]   # 이름 대신 목록 → TypeError 가 아니라 ValueError
        with self.assertRaisesRegex(ValueError, "8번 지출"):
            queries.member_shares(self.store, self.S, self.E)

    def test_bad_period_raises(self):
        # 지출이 없어도 시작일·끝일이 잘못되면 ValueError
        for start, end in (("2026-11-31", self.E), (self.S, "2026-11-31"), (self.S, "x")):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    queries.member_shares(self.store, start, end)
