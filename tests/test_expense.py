"""기능 1(지출 입력·관리) 테스트 — Store.record, history·deleted 자료 항목 경계값 포함."""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import StoreCase  # noqa: E402


class TestHistory(StoreCase):
    def test_history_in_empty(self):
        self.assertIn("history", self.store.data)
        self.assertEqual(self.store.data["history"], [])

    def test_record_add(self):
        after = {"id": 1, "amount": 36000, "payer": "김민수"}
        self.store.record("add", 1, None, after)
        entry = self.store.data["history"][-1]
        self.assertEqual(entry["id"], 1)
        self.assertEqual(entry["action"], "add")
        self.assertIsNone(entry["before"])
        self.assertEqual(entry["after"]["amount"], 36000)

    def test_record_at_format(self):
        self.store.record("add", 1, None, {"id": 1})
        at = self.store.data["history"][-1]["at"]
        self.assertRegex(at, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_record_deepcopy_before(self):
        """before 를 나중에 고쳐도 이력이 바뀌지 않아야 한다."""
        before = {"id": 1, "amount": 36000}
        self.store.record("edit", 1, before, {"id": 1, "amount": 30000})
        before["amount"] = 99999
        self.assertEqual(self.store.data["history"][-1]["before"]["amount"], 36000)

    def test_record_deepcopy_after(self):
        """after 를 나중에 고쳐도 이력이 바뀌지 않아야 한다."""
        after = {"id": 1, "amount": 30000}
        self.store.record("edit", 1, {"id": 1, "amount": 36000}, after)
        after["amount"] = 99999
        self.assertEqual(self.store.data["history"][-1]["after"]["amount"], 30000)

    def test_record_multiple_ordered(self):
        self.store.record("add", 1, None, {"id": 1})
        self.store.record("edit", 1, {"id": 1, "amount": 36000}, {"id": 1, "amount": 30000})
        self.store.record("delete", 1, {"id": 1, "amount": 30000}, {"id": 1, "amount": 30000})
        h = self.store.data["history"]
        self.assertEqual(len(h), 3)
        self.assertEqual([e["action"] for e in h], ["add", "edit", "delete"])

    def test_record_action_variants(self):
        for action in ("add", "edit", "delete", "restore", "undo", "import", "bank", "recurring"):
            self.store.record(action, 1, None, {"id": 1})
        actions = [e["action"] for e in self.store.data["history"]]
        self.assertEqual(actions, ["add", "edit", "delete", "restore", "undo", "import", "bank", "recurring"])

    def test_history_persist_save_load(self):
        """history 가 저장·읽기 후에도 남아야 한다."""
        self.store.record("add", 1, None, {"id": 1, "amount": 36000})
        self.store.save()
        from moim.common.store import Store
        s2 = Store(self.store.path).load()
        self.assertEqual(len(s2.data["history"]), 1)
        self.assertEqual(s2.data["history"][0]["action"], "add")
        self.assertEqual(s2.data["history"][0]["after"]["amount"], 36000)

    def test_old_data_no_history_filled(self):
        """history 없는 옛 자료 파일을 읽으면 빈 목록으로 채워야 한다."""
        old_data = {"members": [], "expenses": [], "next_id": 1}
        with open(self.store.path, "w", encoding="utf-8") as f:
            json.dump(old_data, f)
        from moim.common.store import Store
        s2 = Store(self.store.path).load()
        self.assertIn("history", s2.data)
        self.assertEqual(s2.data["history"], [])


class TestDeleted(StoreCase):
    def test_deleted_compat_missing_key(self):
        """deleted 키 없는 옛 지출도 e.get('deleted', False) 로 False 를 돌려야 한다."""
        self.store.data["expenses"].append({"id": 1, "amount": 1000})
        e = self.store.data["expenses"][0]
        self.assertFalse(e.get("deleted", False))

    def test_deleted_false_explicit(self):
        """deleted=False 인 지출은 삭제되지 않은 것이다."""
        self.store.data["expenses"].append({"id": 1, "amount": 1000, "deleted": False})
        e = self.store.data["expenses"][0]
        self.assertFalse(e.get("deleted", False))

    def test_deleted_true(self):
        """deleted=True 인 지출은 삭제 표시된 것이다."""
        self.store.data["expenses"].append({"id": 1, "amount": 1000, "deleted": True})
        e = self.store.data["expenses"][0]
        self.assertTrue(e.get("deleted", False))


if __name__ == "__main__":
    unittest.main()
