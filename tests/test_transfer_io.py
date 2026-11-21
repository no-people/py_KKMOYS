import datetime as dt
import unittest
from helpers import NAMES, StoreCase
from moim.common import ledger

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
        self.assertEqual(ledger.duplicates(self.store, "2026-11-12", KIM, 36000), [3, 9])

    def test_duplicates_exclude_id(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-12", KIM, 36000, exclude_id=3), [9])

    def test_duplicates_string_amount_and_date_obj(self):
        self.assertEqual(ledger.duplicates(self.store, dt.date(2026, 11, 12), KIM, "36,000"), [3, 9])


if __name__ == "__main__":
    unittest.main()
