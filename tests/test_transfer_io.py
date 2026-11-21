import datetime as dt
import unittest
from helpers import NAMES, StoreCase
from moim.common import dates, ledger, queries

KIM, LEE, PARK = NAMES


class TestLedgerDuplicates(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["expenses"] = [
            {"id": 9, "date": "2026-11-12", "payer": KIM, "amount": 36000, "members": NAMES},
            {"id": 2, "date": "2026-11-12", "payer": KIM, "amount": 36000, "members": NAMES, "deleted": True},
            {"id": 3, "date": "2026-11-12", "payer": KIM, "amount": 36000, "members": NAMES},
            {"id": 4, "date": "2026-11-12", "payer": LEE, "amount": 36000, "members": NAMES},
            {"id": 5, "date": "2026-11-13", "payer": KIM, "amount": 36000, "members": NAMES},
            {"id": 6, "date": "2026-11-12", "payer": KIM, "amount": 12000, "members": NAMES},
        ]

    def test_duplicates_sorted_and_deleted(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-12", KIM, 36000), list((3, 9)))

    def test_duplicates_exclude_id(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-12", KIM, 36000, exclude_id=3), list((9,)))

    def test_duplicates_string_amount_and_date_obj(self):
        self.assertEqual(ledger.duplicates(self.store, dt.date(2026, 11, 12), KIM, "36,000"), list((3, 9)))

    def test_duplicates_empty(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-14", KIM, 36000), [])


class TestCommonDates(StoreCase):
    def test_month_key(self):
        self.assertEqual(dates.month_key("2026-11-12"), "2026-11")
        self.assertEqual(dates.month_key(dt.date(2028, 2, 29)), "2028-02")
        with self.assertRaises(ValueError):
            dates.month_key("2026-02-29")

    def test_is_member_active_extra_cases(self):
        self.store.data["members"] = [
            {"name": KIM, "joined": "2026-09-01"},
            {"name": PARK, "joined": "2026-09-01", "left": "2026-11-15"},
        ]
        self.assertIs(queries.is_member_active(self.store, KIM, dt.date(2026, 11, 10)), True)
        self.assertIs(queries.is_member_active(self.store, PARK, dt.date(2026, 11, 15)), True)
        self.assertIs(queries.is_member_active(self.store, PARK, dt.date(2026, 11, 16)), False)
        with self.assertRaises(ValueError):
            queries.is_member_active(self.store, KIM, "2026-11-31")


if __name__ == "__main__":
    unittest.main()
