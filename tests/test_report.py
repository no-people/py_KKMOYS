from datetime import date
import os
import tempfile
from types import SimpleNamespace
import unittest

from moim.common import queries
from moim.common.store import Store


class TestExpensesIn(unittest.TestCase):
    def test_expenses_in_boundaries_and_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(os.path.join(tmpdir, "data.json"))
            store.data["expenses"] = [
                {"id": 2, "date": "2026-11-10", "amount": 10000},
                {"id": 1, "date": "2026-11-10", "amount": 20000},
                {"id": 3, "date": "2026-11-01", "amount": 5000},
                {"id": 4, "date": "2026-11-30", "amount": 8000},
                {"id": 5, "date": "2026-12-01", "amount": 3000},
                {"id": 6, "date": "2026-11-15", "amount": 7000, "deleted": True},
            ]

            # 1. 시작일(11-01)·끝일(11-30) 포함, 삭제 제외, 날짜순·번호순 정렬 확인
            res = queries.expenses_in(store, "2026-11-01", "2026-11-30")
            self.assertEqual([e["id"] for e in res], [3, 1, 2, 4])

            # 2. include_deleted=True 일 때 삭제 표시 지출 포함 확인
            res_all = queries.expenses_in(store, "2026-11-01", "2026-11-30", include_deleted=True)
            self.assertEqual([e["id"] for e in res_all], [3, 1, 2, 6, 4])


class TestPersonPaid(unittest.TestCase):
    def setUp(self):
        self.store = SimpleNamespace(
            data={
                "expenses": [
                    {
                        "id": 1,
                        "date": "2026-11-01",
                        "payer": "민기슬",
                        "amount": 12000,
                        "members": ["민기슬", "강동휘", "오재원"],
                        "deleted": False,
                    },
                    {
                        "id": 2,
                        "date": "2026-11-15",
                        "payer": "강동휘",
                        "amount": 8000,
                        "members": ["민기슬", "강동휘", "오재원", "염승민"],
                    },
                    {
                        "id": 3,
                        "date": "2026-11-30",
                        "payer": "민기슬",
                        "amount": 5000,
                        "members": ["민기슬", "강동휘"],
                        "deleted": False,
                    },
                    {
                        "id": 4,
                        "date": "2026-11-20",
                        "payer": "민기슬",
                        "amount": 99000,
                        "members": ["민기슬"],
                        "deleted": True,
                    },
                    {
                        "id": 5,
                        "date": "2026-11-18",
                        "payer": "손가인",
                        "amount": 40000,
                        "members": ["손가인", "민기슬"],
                        "deleted": True,
                    },
                    {
                        "id": 6,
                        "date": "2026-10-31",
                        "payer": "오재원",
                        "amount": 30000,
                        "members": ["오재원", "민기슬"],
                    },
                    {
                        "id": 7,
                        "date": "2026-12-01",
                        "payer": "염승민",
                        "amount": 25000,
                        "members": ["염승민", "민기슬"],
                    },
                ]
            }
        )

    def test_person_paid_includes_boundaries_and_excludes_deleted(self):
        result = queries.person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result, {"민기슬": 17000, "강동휘": 8000})

    def test_person_paid_with_date_objects(self):
        result = queries.person_paid(self.store, date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(result, {"민기슬": 17000, "강동휘": 8000})

    def test_person_paid_spec_example_f3(self):
        f3_store = SimpleNamespace(
            data={
                "expenses": [
                    {"id": 1, "date": "2026-11-12", "payer": "이서연", "amount": 6000},
                    {"id": 2, "date": "2026-11-13", "payer": "김민수", "amount": 9000},
                    {"id": 3, "date": "2026-10-15", "payer": "김민수", "amount": 3000},
                ]
            }
        )
        self.assertEqual(
            queries.person_paid(f3_store, "2026-11-10", "2026-11-20"),
            {"이서연": 6000, "김민수": 9000},
        )

    def test_person_paid_excludes_person_with_only_deleted_expenses(self):
        result = queries.person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertNotIn("손가인", result)

    def test_person_paid_excludes_member_who_did_not_pay(self):
        result = queries.person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertNotIn("오재원", result)
        self.assertNotIn("염승민", result)

    def test_person_paid_legacy_store_without_expenses_key(self):
        legacy_store = SimpleNamespace(data={})
        self.assertEqual(queries.person_paid(legacy_store, "2026-11-01", "2026-11-30"), {})

    def test_person_paid_empty_when_no_matching_expenses(self):
        result = queries.person_paid(self.store, "2026-01-01", "2026-01-31")
        self.assertEqual(result, {})


class TestEmptyStoreDateValidation(unittest.TestCase):
    def setUp(self):
        self.empty_store = SimpleNamespace(data={"expenses": []})

    def test_expenses_in_empty_store_returns_empty_list(self):
        self.assertEqual(queries.expenses_in(self.empty_store, "2026-11-01", "2026-11-30"), [])

    def test_person_paid_empty_store_returns_empty_dict(self):
        self.assertEqual(queries.person_paid(self.empty_store, "2026-11-01", "2026-11-30"), {})

    def test_invalid_date_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            queries.expenses_in(self.empty_store, "2026/11/01", "2026-11-30")
        with self.assertRaises(ValueError):
            queries.person_paid(self.empty_store, "2026-11-01", "2026-11-31")

    def test_nonexistent_leap_day_raises_value_error(self):
        with self.assertRaises(ValueError):
            queries.expenses_in(self.empty_store, "2026-02-29", "2026-03-01")
        with self.assertRaises(ValueError):
            queries.person_paid(self.empty_store, "2026-02-01", "2026-02-29")

    def test_leap_year_feb_29_is_accepted(self):
        leap_store = SimpleNamespace(
            data={
                "expenses": [
                    {"id": 1, "date": "2028-02-29", "payer": "민기슬", "amount": 4000},
                ]
            }
        )
        expenses = queries.expenses_in(leap_store, "2028-02-29", "2028-02-29")
        self.assertEqual([e["id"] for e in expenses], [1])
        self.assertEqual(
            queries.person_paid(leap_store, "2028-02-29", "2028-02-29"),
            {"민기슬": 4000},
        )


if __name__ == "__main__":
    unittest.main()