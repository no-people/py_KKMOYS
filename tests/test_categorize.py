"""기능 2 분류 규칙 테스트. 자료 항목 category_fixed 포함."""

import json
import unittest
from datetime import date

from helpers import StoreCase

from moim.common import queries
from moim.common.rules import UNCATEGORIZED
from moim.common.store import Store


class CategoryFixedFormatTest(StoreCase):
    """지출 한 건의 category_fixed 항목: bool. 공통모듈_함수규격.md "지출 한 건의 형식"."""

    # 테스트용 지출 한 건을 만든다. fixed 를 주지 않으면 category_fixed 키가 없는 옛 지출
    def _expense(self, eid, fixed="없음"):
        e = {"id": eid, "date": "2026-11-12", "payer": "김민수", "amount": 9000,
             "members": ["김민수", "이서연"], "category": "식비", "memo": "회의 후 저녁"}
        if fixed != "없음":
            e["category_fixed"] = fixed
        return e

    def test_fixed_true_saved_and_loaded(self):
        # 직접 정한 분류(True)가 저장 후 다시 읽어도 bool True 로 남는다
        self.store.data["expenses"].append(self._expense(1, True))
        self.store.save()
        e = Store(self.store.path).load().get_expense(1)
        self.assertIs(e["category_fixed"], True)

    def test_fixed_false_saved_and_loaded(self):
        # 규칙으로 정한 분류(False)도 그대로 남는다
        self.store.data["expenses"].append(self._expense(1, False))
        self.store.save()
        self.assertIs(Store(self.store.path).load().get_expense(1)["category_fixed"], False)

    def test_old_expense_without_fixed_reads_as_false(self):
        # category_fixed 가 생기기 전의 옛 자료 파일: 읽는 쪽은 e.get("category_fixed", False) 로 False 를 얻는다
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [self._expense(1)], "next_id": 2}, f)
        e = Store(self.path("old.json")).load().get_expense(1)
        self.assertNotIn("category_fixed", e)
        self.assertFalse(e.get("category_fixed", False))


class CategoryOfTest(unittest.TestCase):
    """queries.category_of — 공통모듈_함수규격.md 3-3, 규약 5."""

    def test_category_kept(self):
        self.assertEqual(queries.category_of({"category": "식비"}), "식비")

    def test_none_empty_missing_is_uncategorized(self):
        # None, 빈 문자열, 공백뿐, 키 없음은 모두 "미분류"
        for e in ({"category": None}, {"category": ""}, {"category": " "}, {"category": "  "}, {}):
            with self.subTest(e=e):
                self.assertEqual(queries.category_of(e), UNCATEGORIZED)
        self.assertEqual(UNCATEGORIZED, "미분류")

    def test_surrounding_spaces_stripped(self):
        # 앞뒤 공백은 떼서 돌려준다(" 식비 " 와 "식비" 가 같은 분류)
        self.assertEqual(queries.category_of({"category": " 식비 "}), "식비")

    def test_non_string_category_raises(self):
        # 문자열이 아닌 값은 번호를 붙인 ValueError (규격 0장 오류 약속)
        for bad in (5, ["식비"], True, 3.0, False, 0, []):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "7번 지출의 분류 형식"):
                    queries.category_of({"id": 7, "category": bad})

    def test_fixed_does_not_change_category(self):
        # category_fixed 는 다시 분류할 때만 쓰고, 분류 이름에는 영향이 없다
        for fixed in (True, False):
            with self.subTest(fixed=fixed):
                self.assertEqual(queries.category_of({"category": "식비", "category_fixed": fixed}), "식비")
                self.assertEqual(queries.category_of({"category": None, "category_fixed": fixed}), UNCATEGORIZED)


class CategoryTotalsTest(StoreCase):
    """queries.category_totals — 공통모듈_함수규격.md 3-4."""

    # 지출 dict 를 직접 넣는다(분류 이름·삭제 표시를 마음대로 정하려고)
    def _add(self, eid, day, amount, category=None, deleted=False):
        self.store.data["expenses"].append(
            {"id": eid, "date": day, "payer": "김민수", "amount": amount,
             "members": ["김민수", "이서연"], "category": category, "memo": "", "deleted": deleted})

    def setUp(self):
        super().setUp()
        # 규격 3-4 의 예
        self._add(1, "2026-11-12", 6000, "식비")
        self._add(2, "2026-11-13", 9000, "교통")
        self._add(3, "2026-11-14", 2000, None)
        self._add(4, "2026-11-15", 4000, "식비")

    def test_spec_example(self):
        self.assertEqual(queries.category_totals(self.store, "2026-11-01", "2026-11-30"),
                         {"식비": {"count": 2, "amount": 10000},
                          "교통": {"count": 1, "amount": 9000},
                          "미분류": {"count": 1, "amount": 2000}})

    def test_period_ends_included(self):
        # 시작일(11-01)·끝일(11-30) 당일은 들어가고, 10-31·12-01 은 빠진다(규약 3)
        self._add(5, "2026-11-01", 100, "교통")
        self._add(6, "2026-11-30", 200, "교통")
        self._add(7, "2026-10-31", 1000, "교통")
        self._add(8, "2026-12-01", 1000, "교통")
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["교통"], {"count": 3, "amount": 9300})

    def test_deleted_excluded(self):
        # 삭제 표시된 지출은 건수·금액 모두에서 빠진다(규약 6-1)
        self._add(5, "2026-11-20", 50000, "식비", deleted=True)
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["식비"], {"count": 2, "amount": 10000})

    def test_blank_category_counted_as_uncategorized(self):
        # 빈 문자열·공백뿐인 분류도 "미분류" 한 칸으로 모인다(category_of 와 같은 기준)
        self._add(5, "2026-11-16", 300, "")
        self._add(6, "2026-11-17", 400, " ")
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result[UNCATEGORIZED], {"count": 3, "amount": 2700})
        self.assertNotIn(" ", result)

    def test_spaces_merged_and_old_expense_without_key(self):
        # " 식비 " 는 "식비" 칸으로, category 키가 없는 옛 지출은 "미분류" 칸으로
        self._add(5, "2026-11-16", 500, " 식비 ")
        self.store.data["expenses"].append(
            {"id": 6, "date": "2026-11-17", "payer": "김민수", "amount": 700, "members": ["김민수"]})
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["식비"], {"count": 3, "amount": 10500})
        self.assertEqual(result[UNCATEGORIZED], {"count": 2, "amount": 2700})

    def test_deleted_only_category_absent(self):
        # 삭제 지출만 있는 분류는 결과에 키가 없다(지출이 있는 분류만, 규격 3-4)
        self._add(5, "2026-11-20", 3000, "장소", deleted=True)
        self.assertNotIn("장소", queries.category_totals(self.store, "2026-11-01", "2026-11-30"))

    def test_amount_is_int_won(self):
        # 금액은 period_total 과 같은 money.to_won 으로 더해 int (2.5 → 3, "6,000" → 6000)
        self._add(5, "2026-11-21", 2.5, "교통")
        self._add(6, "2026-11-22", "6,000", "교통")
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["교통"], {"count": 3, "amount": 15003})
        self.assertIsInstance(result["교통"]["amount"], int)

    def test_bad_category_raises(self):
        # 분류 형식이 깨진 지출이 있으면 번호를 붙인 ValueError
        self._add(5, "2026-11-23", 100, 5)
        with self.assertRaisesRegex(ValueError, "5번 지출의 분류 형식"):
            queries.category_totals(self.store, "2026-11-01", "2026-11-30")

    def test_date_object_args(self):
        # 날짜 인자는 date 객체로 줘도 같다(규격 0장)
        self.assertEqual(queries.category_totals(self.store, date(2026, 11, 1), date(2026, 11, 30)),
                         queries.category_totals(self.store, "2026-11-01", "2026-11-30"))

    def test_no_expenses_is_empty(self):
        # 기간에 지출이 없으면 빈 dict(지출이 있는 분류만 돌려준다)
        self.assertEqual(queries.category_totals(self.store, "2026-01-01", "2026-01-31"), {})

    def test_amount_sum_equals_period_total(self):
        # 분류별 금액의 합은 기간 합계(period_total)와 같다(보고서·정산·내보내기 합계 일치용)
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        total = queries.period_total(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(sum(v["amount"] for v in result.values()), total)
