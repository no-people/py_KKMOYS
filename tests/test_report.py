from datetime import date
from types import SimpleNamespace
import unittest

from moim.common import queries


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