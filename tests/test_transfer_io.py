import unittest
from helpers import NAMES, StoreCase
from moim.common import ledger

KIM, LEE, PARK = NAMES


class TestLedgerDuplicates(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["expenses"] = [
            {"id": 1, "date": "2026-11-12", "payer": KIM, "amount": 9000, "members": NAMES},
            {"id": 2, "date": "2026-11-12", "payer": KIM, "amount": 9000, "members": NAMES, "deleted": True},
            {"id": 3, "date": "2026-11-12", "payer": LEE, "amount": 9000, "members": NAMES},
            {"id": 4, "date": "2026-11-13", "payer": KIM, "amount": 9000, "members": NAMES},
        ]

    def test_duplicates_basic_and_deleted(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-12", KIM, 9000), [1])

    def test_duplicates_exclude_id(self):
        self.assertEqual(ledger.duplicates(self.store, "2026-11-12", KIM, 9000, exclude_id=1), [])


if __name__ == "__main__":
    unittest.main()
