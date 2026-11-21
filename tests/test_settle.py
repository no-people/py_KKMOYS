"""기능 4 정산 테스트. 공통 함수 queries.is_locked 와 자료 항목 locks 포함."""

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
