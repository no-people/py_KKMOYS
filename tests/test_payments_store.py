"""공통모듈 규격 0장: 회비 입금 목록과 기존 자료 호환."""
import json

from helpers import NAMES, StoreCase
from moim.common.store import EMPTY, Store


class TestPaymentsStore(StoreCase):
    def test_new_store_has_empty_payments(self):
        self.assertEqual(self.store.data["payments"], [])

    def test_independent_payment_lists(self):
        other = Store(self.path("other.json"))
        self.store.data["payments"].append({"amount": 1})
        self.assertEqual(other.data["payments"], [])
        self.assertEqual(EMPTY["payments"], [])

    def test_old_file_gets_default_without_losing_existing_fields(self):
        old = {"members": [], "expenses": [], "next_id": 7, "extra": {"keep": True}}
        with open(self.store.path, "w", encoding="utf-8") as stream:
            json.dump(old, stream)
        self.store.load()
        self.assertEqual(self.store.data["payments"], [])
        self.assertEqual(self.store.data["next_id"], 7)
        self.assertEqual(self.store.data["extra"], {"keep": True})

    def test_payment_fields_and_sources_survive_save_load(self):
        payments = [
            {"date": "2026-11-02", "member": NAMES[1], "amount": 20000,
             "memo": "11월 회비", "source": "manual"},
            {"date": "2026-11-03", "member": NAMES[0], "amount": 20000,
             "memo": "은행 입금", "source": "bank"},
        ]
        self.store.data["payments"] = payments
        self.store.save()
        loaded = Store(self.store.path).load()
        self.assertEqual(loaded.data["payments"], payments)
