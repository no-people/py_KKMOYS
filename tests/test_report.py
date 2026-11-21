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
                    {"id": 1, "date": "2026-11-01", "payer": "민기슬", "amount": 12000, "deleted": False},
                    {"id": 2, "date": "2026-11-15", "payer": "강동휘", "amount": 8000},
                    {"id": 3, "date": "2026-11-30", "payer": "민기슬", "amount": 5000, "deleted": False},
                    {"id": 4, "date": "2026-11-20", "payer": "민기슬", "amount": 99000, "deleted": True},
                    {"id": 6, "date": "2026-10-31", "payer": "오재원", "amount": 30000},
                    {"id": 7, "date": "2026-12-01", "payer": "염승민", "amount": 25000},
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

    def test_person_paid_legacy_store_without_expenses_key(self):
        legacy_store = SimpleNamespace(data={})
        self.assertEqual(queries.person_paid(legacy_store, "2026-11-01", "2026-11-30"), {})

    def test_person_paid_empty_when_no_matching_expenses(self):
        result = queries.person_paid(self.store, "2026-01-01", "2026-01-31")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()