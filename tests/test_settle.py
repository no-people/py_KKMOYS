"""기능 4 정산 테스트. 공통 함수 queries.is_locked 와 자료 항목 locks 포함."""

import datetime as dt
import json
from unittest import mock

from helpers import StoreCase

from moim import cli
from moim.commands import settle as settle_cmd
from moim.common import ledger, money, queries
from moim.common.store import Store
from moim.features import settle


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

    def test_broken_lock_item_raises(self):
        # 항목 하나가 깨져도 KeyError·TypeError 가 아니라 몇 번째인지 담은 ValueError
        for bad in ({"start": "2026-12-01"}, {"end": "2026-12-31"}, None, "2026-12-01", [],
                    {"start": "2026-12-01", "end": None}, {"start": "2026-12-01", "end": "2026-12-32"}):
            self.store.data["locks"] = [{"start": "2026-10-01", "end": "2026-10-31"}, bad]
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "2번째 확정 기간"):
                queries.is_locked(self.store, "2026-12-15")

    def test_broken_item_found_even_if_earlier_lock_matches(self):
        # 앞 기간에 드는 날짜여도 뒤의 깨진 항목을 넘기지 않는다(날짜에 따라 결과가 달라지지 않게)
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}, {"start": "2026-12-01"}]
        with self.assertRaisesRegex(ValueError, "2번째 확정 기간"):
            queries.is_locked(self.store, "2026-11-15")

    def test_reversed_lock_raises(self):
        self.store.data["locks"] = [{"start": "2026-11-30", "end": "2026-11-01"}]
        with self.assertRaisesRegex(ValueError, "1번째 확정 기간.*시작일이 끝일보다 늦음"):
            queries.is_locked(self.store, "2026-11-15")

    def test_single_day_lock(self):
        # 시작일과 끝일이 같은 하루짜리 확정 기간
        self.store.data["locks"] = [{"start": "2026-11-15", "end": "2026-11-15"}]
        self.assertTrue(queries.is_locked(self.store, "2026-11-15"))
        self.assertFalse(queries.is_locked(self.store, "2026-11-16"))

    def test_insert_with_broken_lock_raises_value_error(self):
        # 호출부(ledger.insert, 기능 1·5·6 이 씀)에도 KeyError 대신 ValueError 로 올라가고 자료는 그대로
        self.store.data["locks"] = [{"start": "2026-11-01"}]
        with self.assertRaisesRegex(ValueError, "1번째 확정 기간"):
            ledger.insert(self.store, "2026-12-05", "김민수", 1000, ["김민수", "이서연"])
        self.assertEqual((self.store.data["expenses"], self.store.data["next_id"]), ([], 1))
        self.assertEqual(self.store.data["history"], [])

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

    def test_amount_read_like_period_total(self):
        # 손으로 고친 자료의 문자열 금액도 period_total·person_paid 와 같은 money.to_won 값으로 나눈다
        self.assertEqual(queries.expense_shares(self._e(amount="6000")), {"김민수": 2000, "이서연": 2000, "박지훈": 2000})
        self.assertEqual(queries.expense_shares(self._e(amount="6,000원")), {"김민수": 2000, "이서연": 2000, "박지훈": 2000})
        # 규약 1 사사오입: "100.5" → 101 원, 남는 2원은 낸 사람(이서연)부터 목록 순서로
        self.assertEqual(queries.expense_shares(self._e(amount="100.5")), {"김민수": 34, "이서연": 34, "박지훈": 33})

    def test_string_zero_amount_same_as_int_zero(self):
        self.assertEqual(queries.expense_shares(self._e(amount="0")), queries.expense_shares(self._e(amount=0)))

    def test_string_negative_amount_rejected(self):
        # 문자열로 바꿔도 음수는 split 이 거부한다(int -1 과 같은 동작)
        for bad in ("-6000", "-0.5"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "음수"):
                queries.expense_shares(self._e(amount=bad))

    def test_bad_amount_raises_value_error(self):
        for bad in ("abc", "Infinity", "-Infinity", "NaN", "sNaN", None, True):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "^금액 형식이 잘못되었습니다"):
                queries.expense_shares(self._e(amount=bad))

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

    def test_string_amount_same_as_person_paid(self):
        # 같은 자료로 낸 돈(person_paid)과 부담(member_shares)의 합이 같다 → 정산 잔액 합 0
        self._add("2026-11-12", "이서연", "6000")
        self._add("2026-11-13", "김민수", "1,000.5")
        shares = queries.member_shares(self.store, self.S, self.E)
        self.assertEqual(sum(shares.values()), sum(queries.person_paid(self.store, self.S, self.E).values()))
        self.assertEqual(sum(shares.values()), 7001)
        self.assertEqual(settle.balance_sum(settle.balances(self.store, self.S, self.E)), 0)

    def test_bad_amount_reported_with_id(self):
        self._add("2026-11-12", "이서연", "Infinity")
        with self.assertRaisesRegex(ValueError, "1번 지출을 나눌 수 없습니다: 금액 형식"):
            queries.member_shares(self.store, self.S, self.E)

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


class BalancesTest(StoreCase):
    """settle.balances·balance_sum. 공고문 기능 4 기본 필수, 규약 2·3·6-1, 잔액 = 낸 돈 - 부담 + 보낸 송금 - 받은 송금."""

    S, E = "2026-11-10", "2026-11-20"
    KIM, LEE, PARK = "김민수", "이서연", "박지훈"

    def _add(self, date, payer, amount, members=None, weights=None, deleted=False):
        e = {"id": self.store.new_id(), "date": date, "payer": payer, "amount": amount,
             "members": members or [self.KIM, self.LEE, self.PARK], "weights": weights,
             "category": None, "memo": "", "deleted": deleted, "recurring_id": None}
        self.store.data["expenses"].append(e)
        return e

    def _send(self, date, frm, to, amount):
        self.store.data["transfers"].append({"date": date, "from": frm, "to": to, "amount": amount})

    def rows(self):
        return settle.balances(self.store, self.S, self.E)

    def test_basic_balance(self):
        # 기본 테스트 F4 test_balance 와 같은 값: 9,000 을 3명이 → 김민수 낸 돈 9000, 부담 3000, 잔액 6000
        self._add("2026-11-12", self.KIM, 9000)
        r = self.rows()[self.KIM]
        self.assertEqual((r["paid"], r["owed"], r["sent"], r["received"], r["balance"]), (9000, 3000, 0, 0, 6000))
        self.assertEqual(self.rows()[self.LEE]["balance"], -3000)

    def test_even_split(self):
        self._add("2026-11-12", self.LEE, 6000)
        self.assertEqual({n: r["owed"] for n, r in self.rows().items()}, {self.KIM: 2000, self.LEE: 2000, self.PARK: 2000})

    def test_remainder_to_payer(self):
        # 규약 2: 10,000 / 3 = 3333 남는 1원은 낸 사람(박지훈)
        self._add("2026-11-12", self.PARK, 10000)
        rows = self.rows()
        self.assertEqual({n: r["owed"] for n, r in rows.items()}, {self.KIM: 3333, self.LEE: 3333, self.PARK: 3334})
        self.assertEqual(settle.balance_sum(rows), 0)

    def test_weights(self):
        # 가중치 2:1:1, 101원 → 50·25·26(남는 1원은 낸 사람 박지훈)
        self._add("2026-11-12", self.PARK, 101, weights={self.KIM: 2, self.LEE: 1, self.PARK: 1})
        self.assertEqual({n: r["owed"] for n, r in self.rows().items()}, {self.KIM: 50, self.LEE: 25, self.PARK: 26})

    def test_period_ends_included(self):
        # 규약 3: 시작일·끝일 포함, 밖은 빠짐
        self._add("2026-11-09", self.KIM, 3000)
        self._add("2026-11-10", self.KIM, 3000)
        self._add("2026-11-20", self.KIM, 6000)
        self._add("2026-11-21", self.KIM, 3000)
        self.assertEqual(self.rows()[self.KIM]["paid"], 9000)

    def test_deleted_excluded(self):
        # 규약 6-1: 삭제 표시된 지출은 정산에서 빠진다
        self._add("2026-11-12", self.KIM, 9000)
        self._add("2026-11-13", self.LEE, 3000, deleted=True)
        rows = self.rows()
        self.assertEqual((rows[self.LEE]["paid"], rows[self.LEE]["owed"]), (0, 3000))

    def test_payer_not_member(self):
        # 낸 사람이 참여자가 아니면 부담 0, 낸 돈 전액이 받을 돈
        self._add("2026-11-12", self.KIM, 6000, members=[self.LEE, self.PARK])
        rows = self.rows()
        self.assertEqual((rows[self.KIM]["owed"], rows[self.KIM]["balance"]), (0, 6000))
        self.assertEqual(settle.balance_sum(rows), 0)

    def test_transfers(self):
        # 이서연이 김민수에게 3,000 보냄 → 이서연 잔액 0, 김민수 6000 - 3000 = 3000
        self._add("2026-11-12", self.KIM, 9000)
        self._send("2026-11-15", self.LEE, self.KIM, 3000)
        rows = self.rows()
        self.assertEqual((rows[self.LEE]["sent"], rows[self.LEE]["balance"]), (3000, 0))
        self.assertEqual((rows[self.KIM]["received"], rows[self.KIM]["balance"]), (3000, 3000))
        self.assertEqual(settle.balance_sum(rows), 0)

    def test_transfer_outside_period_ignored(self):
        self._add("2026-11-12", self.KIM, 9000)
        self._send("2026-11-21", self.LEE, self.KIM, 3000)
        self.assertEqual(self.rows()[self.LEE]["sent"], 0)

    def test_transfers_null_or_missing(self):
        self._add("2026-11-12", self.KIM, 9000)
        self.store.data["transfers"] = None
        self.assertEqual(self.rows()[self.KIM]["balance"], 6000)
        del self.store.data["transfers"]
        self.assertEqual(self.rows()[self.KIM]["balance"], 6000)

    def test_transfers_bad_shape(self):
        self.store.data["transfers"] = {"date": "2026-11-12"}
        with self.assertRaisesRegex(ValueError, "transfers 형식"):
            self.rows()

    def test_broken_transfer_item(self):
        self._send("2026-11-12", self.LEE, self.KIM, 1000)
        self.store.data["transfers"].append({"date": "2026-11-13", "from": self.LEE, "amount": 1000})
        with self.assertRaisesRegex(ValueError, "2번째 송금 기록"):
            self.rows()

    def test_zero_transfer_rejected(self):
        self._send("2026-11-12", self.LEE, self.KIM, 0)
        with self.assertRaisesRegex(ValueError, "1번째 송금 기록"):
            self.rows()

    def test_bad_transfer_names_rejected(self):
        # 이름이 문자열이 아니거나 비었거나, 자기 자신에게 보낸 기록은 번호를 붙여 거부
        for frm, to in [(None, self.KIM), (["가"], self.KIM), (self.LEE, " "), (self.KIM, self.KIM)]:
            self.store.data["transfers"] = [{"date": "2026-11-12", "from": frm, "to": to, "amount": 1000}]
            with self.subTest(frm=frm, to=to), self.assertRaisesRegex(ValueError, "1번째 송금 기록"):
                self.rows()

    def test_roster_order(self):
        # 명부 순서(김민수, 이서연, 박지훈). 낸 순서와 상관없음
        self._add("2026-11-12", self.PARK, 300)
        self.assertEqual(list(self.rows()), [self.KIM, self.LEE, self.PARK])

    def test_empty_period(self):
        self.assertEqual(self.rows(), {})
        self.assertEqual(settle.balance_sum({}), 0)

    def test_int_values(self):
        self._add("2026-11-12", self.KIM, 10000)
        for row in self.rows().values():
            for v in row.values():
                self.assertIs(type(v), int)

    def test_many_expenses_sum_zero(self):
        for i, (payer, amount) in enumerate([(self.KIM, 10001), (self.LEE, 7), (self.PARK, 33333), (self.KIM, 1)]):
            self._add(f"2026-11-{11 + i}", payer, amount)
        self._add("2026-11-16", self.LEE, 1000, members=[self.KIM, self.PARK], weights={self.KIM: 3, self.PARK: 1})
        self._send("2026-11-17", self.PARK, self.KIM, 2500)
        self.assertEqual(settle.balance_sum(self.rows()), 0)

    def test_bad_dates(self):
        with self.assertRaises(ValueError):
            settle.balances(self.store, "2026-11-31", self.E)
        with self.assertRaisesRegex(ValueError, "기간이 잘못"):
            settle.balances(self.store, self.E, self.S)

    def test_date_objects(self):
        self._add("2026-11-12", self.KIM, 9000)
        self.assertEqual(settle.balances(self.store, dt.date(2026, 11, 10), dt.date(2026, 11, 20))[self.KIM]["balance"], 6000)

    def test_broken_expense_reported(self):
        self._add("2026-11-12", self.KIM, 9000, members="김민수")
        with self.assertRaisesRegex(ValueError, "1번 지출"):
            self.rows()


class SettleBalanceCommandTest(StoreCase):
    """명령 settle balance. 스켈레톤 PDF 8절 정산 결과 화면(열·잔액 합계 줄), 기간 인자, 저장 안 함."""

    KIM, LEE, PARK = "김민수", "이서연", "박지훈"

    def _add(self, date, payer, amount, members=None, deleted=False):
        self.store.data["expenses"].append({
            "id": self.store.new_id(), "date": date, "payer": payer, "amount": amount,
            "members": members or [self.KIM, self.LEE, self.PARK], "weights": None, "category": None,
            "memo": "", "deleted": deleted, "recurring_id": None})

    def _send(self, date, frm, to, amount):
        self.store.data["transfers"].append({"date": date, "from": frm, "to": to, "amount": amount})

    def call(self, *argv):
        lines = []
        args = cli.build_parser().parse_args(["settle", *argv])
        changed = cli.run(args, self.cfg, self.store, lines.append)
        return changed, lines

    def test_month_table(self):
        self._add("2026-11-12", self.KIM, 9000)
        changed, lines = self.call("balance", "--month", "2026-11")
        self.assertFalse(changed)   # 보기만 하므로 저장하지 않는다
        self.assertEqual(lines[0].split(), ["이름", "낸", "돈", "부담", "보낸", "송금", "받은", "송금", "잔액"])
        self.assertEqual(lines[2].split(), [self.KIM, "9,000", "3,000", "0", "0", "6,000"])
        self.assertEqual(lines[3].split(), [self.LEE, "0", "3,000", "0", "0", "-3,000"])
        self.assertEqual(lines[4].split(), [self.PARK, "0", "3,000", "0", "0", "-3,000"])
        self.assertEqual(lines[-1], "잔액 합계: 0")
        self.assertEqual(len(lines), 6)

    def test_start_end_period(self):
        # 규약 3: 시작일·끝일 포함, 전날·다음 날은 빠짐
        self._add("2026-11-09", self.KIM, 3000)
        self._add("2026-11-10", self.KIM, 3000)
        self._add("2026-11-20", self.LEE, 3000)
        self._add("2026-11-21", self.LEE, 6000)
        _, lines = self.call("balance", "--start", "2026-11-10", "--end", "2026-11-20")
        self.assertEqual(lines[2].split()[:3], [self.KIM, "3,000", "2,000"])
        self.assertEqual(lines[3].split()[:3], [self.LEE, "3,000", "2,000"])

    def test_remainder_shown(self):
        # 규약 2: 10,000 / 3 → 낸 사람 박지훈 3,334
        self._add("2026-11-12", self.PARK, 10000)
        _, lines = self.call("balance", "--month", "2026-11")
        self.assertEqual(lines[4].split()[:3], [self.PARK, "10,000", "3,334"])
        self.assertEqual(lines[-1], "잔액 합계: 0")

    def test_transfer_columns(self):
        # 이서연이 김민수에게 3,000 보냄 → 송금 열에 보이고 잔액에 반영
        self._add("2026-11-12", self.KIM, 9000)
        self._send("2026-11-15", self.LEE, self.KIM, 3000)
        _, lines = self.call("balance", "--month", "2026-11")
        self.assertEqual(lines[2].split(), [self.KIM, "9,000", "3,000", "0", "3,000", "3,000"])
        self.assertEqual(lines[3].split(), [self.LEE, "0", "3,000", "3,000", "0", "0"])
        self.assertEqual(lines[-1], "잔액 합계: 0")

    def test_deleted_expense_not_shown(self):
        # 규약 6-1: 삭제 표시된 지출은 정산에서 빠진다
        self._add("2026-11-12", self.KIM, 9000)
        self._add("2026-11-13", self.LEE, 999999, deleted=True)
        _, lines = self.call("balance", "--month", "2026-11")
        self.assertEqual(lines[3].split()[:3], [self.LEE, "0", "3,000"])
        self.assertNotIn("999,999", "\n".join(lines))

    def test_balance_lines_exact(self):
        # 명령 출력 전체: textfmt.table(규격 6-1) 모양 — 머리줄 왼쪽 정렬, 열마다 - 줄, 숫자 열 오른쪽 정렬, 한글 2칸
        rows = {self.KIM: {"paid": 1234567, "owed": 3000, "sent": 0, "received": 0, "balance": 1231567},
                "Al": {"paid": 0, "owed": 1231567, "sent": 0, "received": 0, "balance": -1231567}}
        self.assertEqual(settle_cmd.balance_lines(rows), [
            "이름    낸 돈      부담       보낸 송금  받은 송금  잔액",
            "------  ---------  ---------  ---------  ---------  ----------",
            "김민수  1,234,567      3,000          0          0   1,231,567",
            "Al              0  1,231,567          0          0  -1,231,567",
            "잔액 합계: 0",
        ])

    def test_empty_period(self):
        _, lines = self.call("balance", "--month", "2026-11")
        self.assertEqual(lines, ["이 기간에 정산할 지출·송금이 없습니다"])

    def test_nonzero_sum_warning(self):
        rows = {self.KIM: {"paid": 100, "owed": 0, "sent": 0, "received": 0, "balance": 100}}
        with mock.patch.object(settle, "balances", return_value=rows):
            _, lines = self.call("balance", "--month", "2026-11")
        self.assertEqual(lines[-1], "잔액 합계: 100 (경고: 0이 아닙니다. 자료를 확인하십시오)")

    def test_period_required(self):
        with self.assertRaisesRegex(ValueError, "기간을 지정"):
            self.call("balance")

    def test_bad_month(self):
        with self.assertRaisesRegex(ValueError, "달 형식"):
            self.call("balance", "--month", "2026-13")

    def test_subcommand_required(self):
        with self.assertRaisesRegex(cli.UsageError, "cmd"):
            cli.build_parser().parse_args(["settle"])

    def test_does_not_change_data(self):
        self._add("2026-11-12", self.KIM, 9000)
        before = repr(self.store.data)
        self.call("balance", "--month", "2026-11")
        self.assertEqual(repr(self.store.data), before)


class MinimalTransfersTest(StoreCase):
    """settle.minimal_transfers 와 명령 settle transfers. 공고문 기능 4 확장 필수 "송금 횟수를 줄인 누가 누구에게 얼마"."""

    KIM, LEE, PARK = "김민수", "이서연", "박지훈"

    @staticmethod
    def rows(**balances):
        return {name: {"paid": 0, "owed": 0, "sent": 0, "received": 0, "balance": b} for name, b in balances.items()}

    def settle_all(self, rows, transfers):
        # 송금을 그대로 반영하면 모든 잔액이 0 이 되는지
        left = {name: r["balance"] for name, r in rows.items()}
        for frm, to, won in transfers:
            self.assertGreater(won, 0)
            left[frm] += won
            left[to] -= won
        return left

    def _add(self, date, payer, amount, members=None):
        self.store.data["expenses"].append({
            "id": self.store.new_id(), "date": date, "payer": payer, "amount": amount,
            "members": members or [self.KIM, self.LEE, self.PARK], "weights": None, "category": None,
            "memo": "", "deleted": False, "recurring_id": None})

    def test_basic(self):
        # 김민수가 9,000 낸 경우: 이서연·박지훈이 3,000씩. 금액이 같으면 rows(명부) 순서
        rows = self.rows(김민수=6000, 이서연=-3000, 박지훈=-3000)
        self.assertEqual(settle.minimal_transfers(rows), [(self.LEE, self.KIM, 3000), (self.PARK, self.KIM, 3000)])

    def test_largest_first(self):
        # 가장 많이 보낼 사람(C 120)이 가장 많이 받을 사람(A 100)에게 먼저 보낸다
        rows = self.rows(A=100, B=50, C=-120, D=-30)
        self.assertEqual(settle.minimal_transfers(rows), [("C", "A", 100), ("D", "B", 30), ("C", "B", 20)])

    def test_count_at_most_people_minus_one_and_all_settled(self):
        import random
        rng = random.Random(4)
        for _ in range(300):
            n = rng.randint(1, 7)
            vals = [rng.randint(-50000, 50000) for _ in range(n - 1)]
            vals.append(-sum(vals))
            rows = self.rows(**{f"p{i}": v for i, v in enumerate(vals)})
            transfers = settle.minimal_transfers(rows)
            self.assertLessEqual(len(transfers), max(n - 1, 0))
            self.assertEqual(self.settle_all(rows, transfers), {name: 0 for name in rows})   # 실패하면 남은 잔액이 보인다

    def test_no_transfer_when_all_zero_or_empty(self):
        self.assertEqual(settle.minimal_transfers(self.rows(김민수=0, 이서연=0)), [])
        self.assertEqual(settle.minimal_transfers({}), [])

    def test_one_won(self):
        self.assertEqual(settle.minimal_transfers(self.rows(김민수=1, 이서연=-1)), [(self.LEE, self.KIM, 1)])

    def test_nonzero_sum_raises(self):
        with self.assertRaisesRegex(ValueError, "잔액 합이 0이 아니라"):
            settle.minimal_transfers(self.rows(김민수=100, 이서연=-99))

    def test_bad_balance_raises(self):
        for bad in ("100", 1.5, None, True):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "원 단위 정수"):
                settle.minimal_transfers(self.rows(김민수=bad, 이서연=-100))

    def test_broken_row_raises(self):
        for bad in ({}, None, [1]):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "김민수의 잔액이 없습니다"):
                settle.minimal_transfers({"김민수": bad, "이서연": {"balance": 0}})

    def test_does_not_change_rows(self):
        rows = self.rows(김민수=6000, 이서연=-3000, 박지훈=-3000)
        before = repr(rows)
        settle.minimal_transfers(rows)
        self.assertEqual(repr(rows), before)

    def test_from_balances_with_remainder_and_recorded_transfer(self):
        # 10,000 을 박지훈이 냄(3334/3333/3333) + 이서연이 이미 1,000 보냄 → 남은 것만 송금
        self._add("2026-11-12", self.PARK, 10000)
        self.store.data["transfers"].append({"date": "2026-11-13", "from": self.LEE, "to": self.PARK, "amount": 1000})
        rows = settle.balances(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(settle.minimal_transfers(rows), [(self.KIM, self.PARK, 3333), (self.LEE, self.PARK, 2333)])

    def call(self, *argv):
        lines = []
        args = cli.build_parser().parse_args(["settle", *argv])
        changed = cli.run(args, self.cfg, self.store, lines.append)
        return changed, lines

    def test_command_output(self):
        # 스켈레톤 PDF 8절 송금 목록 화면 모양: "이름 -> 이름 금액원"
        self._add("2026-11-12", self.KIM, 9000)
        changed, lines = self.call("transfers", "--month", "2026-11")
        self.assertFalse(changed)
        self.assertEqual(lines, ["이서연 -> 김민수 3,000원", "박지훈 -> 김민수 3,000원"])

    def test_command_period_and_empty(self):
        self._add("2026-11-09", self.KIM, 9000)
        _, lines = self.call("transfers", "--start", "2026-11-10", "--end", "2026-11-20")
        self.assertEqual(lines, ["보낼 송금이 없습니다"])
        with self.assertRaisesRegex(ValueError, "기간을 지정"):
            self.call("transfers")

    def test_command_does_not_change_data(self):
        self._add("2026-11-12", self.KIM, 9000)
        before = repr(self.store.data)
        self.call("transfers", "--month", "2026-11")
        self.assertEqual(repr(self.store.data), before)


class TransfersFormatTest(StoreCase):
    """자료 항목 transfers: [{"date", "from", "to", "amount"}]. 공통모듈_함수규격.md "EMPTY 에 새로 추가할 최상위 항목"."""

    def test_empty_has_transfers(self):
        self.assertEqual(Store(self.path("new.json")).load().data["transfers"], [])

    def test_saved_and_loaded(self):
        t = {"date": "2026-11-21", "from": "이서연", "to": "김민수", "amount": 3000}
        self.store.data["transfers"].append(t)
        self.store.save()
        loaded = Store(self.store.path).load().data["transfers"]
        self.assertEqual(loaded, [t])
        self.assertIs(type(loaded[0]["amount"]), int)

    def test_old_file_without_transfers(self):
        # transfers 가 생기기 전의 옛 자료 파일도 읽으면 기본값 [] 로 채워진다
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1}, f)
        self.assertEqual(Store(self.path("old.json")).load().data["transfers"], [])

    def test_existing_transfers_kept_on_load(self):
        # 이미 있는 송금 기록을 기본값으로 덮어쓰지 않는다
        t = {"date": "2026-11-21", "from": "박지훈", "to": "김민수", "amount": 1}
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1, "transfers": [t]}, f)
        self.assertEqual(Store(self.path("old.json")).load().data["transfers"], [t])
