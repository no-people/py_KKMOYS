"""기능 1(지출 입력·관리) 테스트 — Store.record, history·deleted 자료 항목 경계값 포함."""

import json
import os
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

    def test_record_deepcopy_nested(self):
        """안쪽 목록·dict(members·weights)를 나중에 고쳐도 이력이 바뀌지 않아야 한다(얕은 복사면 실패)."""
        before = {"id": 1, "members": ["김민수"], "weights": {"김민수": 1}}
        self.store.record("edit", 1, before, before)
        before["members"].append("이서연")
        before["weights"]["김민수"] = 9
        entry = self.store.data["history"][-1]
        for side in ("before", "after"):
            self.assertEqual(entry[side]["members"], ["김민수"])
            self.assertEqual(entry[side]["weights"], {"김민수": 1})

    def test_record_history_key_missing(self):
        del self.store.data["history"]
        self.store.record("add", 1, None, {"id": 1})
        self.assertEqual(len(self.store.data["history"]), 1)

    def test_record_history_bad_type(self):
        """history 가 목록도 null 도 아니면 조용히 지우지 않고 ValueError."""
        self.store.data["history"] = {"broken": 1}
        with self.assertRaises(ValueError):
            self.store.record("add", 1, None, {"id": 1})
        self.assertEqual(self.store.data["history"], {"broken": 1})

    def test_record_after_none(self):
        """after 에 None 을 넘기면 이력의 after 도 None 이어야 한다."""
        self.store.record("delete", 1, {"id": 1, "amount": 36000}, None)
        entry = self.store.data["history"][-1]
        self.assertEqual(entry["before"]["amount"], 36000)
        self.assertIsNone(entry["after"])

    def test_record_returns_none(self):
        self.assertIsNone(self.store.record("add", 1, None, {"id": 1}))

    def test_record_does_not_save(self):
        """record 는 저장하지 않는다. save 없이 다시 읽으면 이력이 없어야 한다."""
        self.store.record("add", 1, None, {"id": 1})
        from moim.common.store import Store
        s2 = Store(self.store.path).load()
        self.assertEqual(s2.data["history"], [])

    def test_record_history_null_in_file(self):
        """옛 파일에 "history": null 이 있어도 record 가 실패하지 않아야 한다."""
        with open(self.store.path, "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1, "history": None}, f)
        from moim.common.store import Store
        s2 = Store(self.store.path).load()
        s2.record("add", 1, None, {"id": 1})
        self.assertEqual(len(s2.data["history"]), 1)


class TestDeleted(StoreCase):
    """deleted 표시가 실제 조회 함수(queries.expenses_in)에서 어떻게 다뤄지는지 본다."""

    def _put(self, eid, **extra):
        e = {"id": eid, "date": "2026-11-10", "payer": "김민수", "amount": 1000, "members": ["김민수"]}
        e.update(extra)
        self.store.data["expenses"].append(e)

    def test_deleted_missing_key_is_not_deleted(self):
        """deleted 키 없는 옛 지출은 삭제되지 않은 것으로 본다(기본 조회에 나온다)."""
        from moim.common.queries import expenses_in
        self._put(1)
        self.assertEqual([e["id"] for e in expenses_in(self.store, "2026-11-01", "2026-11-30")], [1])

    def test_deleted_true_excluded_by_default(self):
        from moim.common.queries import expenses_in
        self._put(1, deleted=False)
        self._put(2, deleted=True)
        self.assertEqual([e["id"] for e in expenses_in(self.store, "2026-11-01", "2026-11-30")], [1])

    def test_deleted_true_included_when_asked(self):
        from moim.common.queries import expenses_in
        self._put(1, deleted=False)
        self._put(2, deleted=True)
        got = expenses_in(self.store, "2026-11-01", "2026-11-30", include_deleted=True)
        self.assertEqual([e["id"] for e in got], [1, 2])

    def test_old_file_expense_without_deleted_loads(self):
        """deleted 없는 옛 지출이 든 파일을 읽어도 지출이 그대로 남고 조회된다."""
        from moim.common.queries import expenses_in
        from moim.common.store import Store
        self._put(1)
        self.store.save()
        s2 = Store(self.store.path).load()
        self.assertNotIn("deleted", s2.data["expenses"][0])
        self.assertEqual(len(expenses_in(s2, "2026-11-01", "2026-11-30")), 1)


class TestManageExpense(StoreCase):
    """list_expenses·edit_expense·delete_expense·restore_expense. 자료는 ledger.insert 로 만든다."""

    def put(self, date="2026-11-12", payer="김민수", amount=36000, members=("김민수", "이서연"), **kw):
        from moim.common import ledger
        return ledger.insert(self.store, date, payer, amount, list(members), **kw)

    def snapshot(self):
        d = self.store.data
        return json.dumps([d["expenses"], d["history"], d["next_id"]], ensure_ascii=False)

    def lock_november(self):
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]

    # --- list_expenses
    def test_list_orders(self):
        from moim.features.expenses import list_expenses
        a = self.put("2026-11-20", amount=3000)
        b = self.put("2026-11-05", amount=9000)
        c = self.put("2026-11-05", amount=1000)
        ids = lambda order: [e["id"] for e in list_expenses(self.store, order=order)]
        self.assertEqual(ids("id"), [a["id"], b["id"], c["id"]])
        self.assertEqual(ids("date"), [b["id"], c["id"], a["id"]])   # 같은 날이면 번호순
        self.assertEqual(ids("amount"), [c["id"], a["id"], b["id"]])
        with self.assertRaisesRegex(ValueError, "정렬 기준"):
            list_expenses(self.store, order="payer")

    def test_list_deleted_hidden_unless_asked(self):
        from moim.features.expenses import list_expenses
        a = self.put()
        b = self.put(amount=1000)
        b["deleted"] = True
        del a["deleted"]   # deleted 키 없는 옛 지출은 삭제되지 않은 것
        self.assertEqual([e["id"] for e in list_expenses(self.store)], [a["id"]])
        self.assertEqual([e["id"] for e in list_expenses(self.store, include_deleted=True)], [a["id"], b["id"]])

    # --- edit_expense
    def test_edit_amount_and_history(self):
        from moim.features.expenses import edit_expense
        e = self.put()
        got, warnings = edit_expense(self.store, e["id"], amount="6,000원", memo="고침")
        self.assertIs(got, e)
        self.assertEqual((e["amount"], e["memo"], warnings), (6000, "고침", []))
        h = self.store.data["history"][-1]
        self.assertEqual((h["id"], h["action"], h["before"]["amount"], h["after"]["amount"]),
                         (e["id"], "edit", 36000, 6000))
        self.assertEqual(len(self.store.data["history"]), 2)   # add + edit

    def test_edit_date_members_weights(self):
        from datetime import date
        from moim.features.expenses import edit_expense
        e = self.put()
        edit_expense(self.store, e["id"], date=date(2026, 11, 13), members=["이서연", "박지훈"],
                     weights={"이서연": 2, "박지훈": 1})
        self.assertEqual((e["date"], e["members"], e["weights"]),
                         ("2026-11-13", ["이서연", "박지훈"], {"이서연": 2, "박지훈": 1}))
        self.assertFalse(e["category_fixed"])

    def test_edit_rejects_and_keeps_data(self):
        from moim.features.expenses import edit_expense
        e = self.put()
        w = self.put(amount=1000, weights={"김민수": 1, "이서연": 1})
        cases = ((e["id"], {"amount": 0}), (e["id"], {"members": []}), (e["id"], {"payer": "없는사람"}),
                 (e["id"], {"date": "2026-11-31"}), (e["id"], {"id": 9}), (e["id"], {"deleted": True}),
                 (e["id"], {}), (99, {"amount": 1000}), (w["id"], {"members": ["김민수"]}))   # 마지막: 비율 불일치
        for eid, changes in cases:
            before = self.snapshot()
            with self.assertRaises(ValueError, msg=(eid, changes)):
                edit_expense(self.store, eid, **changes)
            self.assertEqual(self.snapshot(), before, (eid, changes))

    def test_edit_payer_not_in_members_ok(self):
        from moim.features.expenses import edit_expense
        e = self.put()
        edit_expense(self.store, e["id"], payer="박지훈")   # 낸 사람이 참여자가 아니어도 된다(규약 6-2)
        self.assertEqual((e["payer"], e["members"]), ("박지훈", ["김민수", "이서연"]))

    def test_edit_weights_to_none(self):
        from moim.features.expenses import edit_expense
        e = self.put(weights={"김민수": 2, "이서연": 1})
        edit_expense(self.store, e["id"], weights=None)   # 균등 분배로 돌아감
        self.assertIsNone(e["weights"])
        self.assertEqual(self.store.data["history"][-1]["before"]["weights"], {"김민수": 2, "이서연": 1})

    def test_edit_deleted_rejected(self):
        from moim.features.expenses import edit_expense
        e = self.put()
        e["deleted"] = True
        with self.assertRaisesRegex(ValueError, "삭제된 지출"):
            edit_expense(self.store, e["id"], amount=1000)

    def test_edit_locked_both_dates(self):
        from moim.features.expenses import edit_expense
        inside = self.put("2026-11-30")
        outside = self.put("2026-12-01")
        self.lock_november()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "정산이 확정된 기간입니다: 2026-11-30"):
            edit_expense(self.store, inside["id"], amount=1000)   # 끝일의 지출을 고치기
        with self.assertRaisesRegex(ValueError, "정산이 확정된 기간입니다: 2026-11-30"):
            edit_expense(self.store, inside["id"], date="2026-12-02")   # 확정 기간 밖으로 빼기
        with self.assertRaisesRegex(ValueError, "정산이 확정된 기간입니다: 2026-11-30"):
            edit_expense(self.store, outside["id"], date="2026-11-30")   # 확정 기간 안으로 옮기기
        self.assertEqual(self.snapshot(), before)
        edit_expense(self.store, outside["id"], date="2026-12-02")
        self.assertEqual(outside["date"], "2026-12-02")

    def test_edit_duplicate_warning_excludes_self(self):
        from moim.features.expenses import edit_expense
        a = self.put(amount=1000)
        b = self.put(amount=2000)
        _, warnings = edit_expense(self.store, a["id"], memo="메모만")
        self.assertEqual(warnings, [])   # 자기 자신은 중복이 아니다
        _, warnings = edit_expense(self.store, b["id"], amount=1000)
        self.assertEqual(len(warnings), 1)
        self.assertIn(f"({a['id']}번)", warnings[0])

    def test_edit_to_after_left_rejected(self):
        from moim.features.expenses import edit_expense
        self.store.member("이서연")["left"] = "2026-11-15"
        e = self.put("2026-11-12")
        edit_expense(self.store, e["id"], date="2026-11-15")   # 탈퇴일 당일은 된다
        with self.assertRaisesRegex(ValueError, "이서연"):
            edit_expense(self.store, e["id"], date="2026-11-16")
        self.assertEqual(e["date"], "2026-11-15")

    # --- delete_expense / restore_expense
    def test_delete_restore_cycle(self):
        from moim.features.expenses import delete_expense, list_expenses, restore_expense
        e = self.put()
        self.assertIs(delete_expense(self.store, e["id"]), e)
        self.assertTrue(e["deleted"])
        self.assertEqual(list_expenses(self.store), [])
        self.assertIn(e, self.store.data["expenses"])   # 지우지 않고 표시만(규약 6-1)
        with self.assertRaisesRegex(ValueError, "이미 삭제된"):
            delete_expense(self.store, e["id"])
        restore_expense(self.store, e["id"])
        self.assertFalse(e["deleted"])
        with self.assertRaisesRegex(ValueError, "삭제되지 않은"):
            restore_expense(self.store, e["id"])
        h = self.store.data["history"]
        self.assertEqual([x["action"] for x in h], ["add", "delete", "restore"])
        self.assertEqual((h[1]["before"]["deleted"], h[1]["after"]["deleted"]), (False, True))

    def test_delete_restore_locked(self):
        from moim.features.expenses import delete_expense, restore_expense
        a = self.put("2026-11-01")
        b = self.put("2026-11-02", amount=1000)
        b["deleted"] = True
        self.lock_november()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "정산이 확정된 기간입니다: 2026-11-01"):
            delete_expense(self.store, a["id"])   # 시작일
        with self.assertRaisesRegex(ValueError, "정산이 확정된 기간입니다: 2026-11-02"):
            restore_expense(self.store, b["id"])
        self.assertEqual(self.snapshot(), before)

    def test_delete_locked_end_day(self):
        from moim.features.expenses import delete_expense
        end = self.put("2026-11-30")
        nxt = self.put("2026-12-01", amount=1000)
        self.lock_november()
        with self.assertRaisesRegex(ValueError, "정산이 확정된 기간입니다: 2026-11-30"):
            delete_expense(self.store, end["id"])
        self.assertFalse(end["deleted"])
        delete_expense(self.store, nxt["id"])   # 끝일 다음 날은 된다
        self.assertTrue(nxt["deleted"])

    # --- #44: is_locked 가 ValueError 를 낼 때
    def test_corrupt_stored_date_rejected_with_id(self):
        from moim.features.expenses import delete_expense, edit_expense
        e = self.put()
        e["date"] = "2026/11/12"   # 옛 파일의 깨진 날짜
        before = self.snapshot()
        for call in (lambda: edit_expense(self.store, e["id"], amount=1000),
                     lambda: delete_expense(self.store, e["id"])):
            with self.assertRaisesRegex(ValueError, f"{e['id']}번 지출: 날짜가 잘못되었습니다"):
                call()
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_locks_not_treated_as_unlocked(self):
        from moim.features.expenses import delete_expense
        e = self.put()
        self.store.data["locks"] = {"start": "2026-11-01"}   # 목록이 아님
        with self.assertRaisesRegex(ValueError, "locks 형식"):
            delete_expense(self.store, e["id"])
        self.assertFalse(e["deleted"])

    def test_broken_history_keeps_expense(self):
        from moim.features.expenses import delete_expense, edit_expense
        e = self.put()
        self.store.data["history"] = {"broken": 1}
        for call in (lambda: edit_expense(self.store, e["id"], amount=1000),
                     lambda: delete_expense(self.store, e["id"])):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual((e["amount"], e["deleted"]), (36000, False))

    def test_does_not_save(self):
        from moim.common.store import Store
        from moim.features.expenses import delete_expense, edit_expense
        e = self.put()
        self.store.save()
        edit_expense(self.store, e["id"], amount=1000)
        delete_expense(self.store, e["id"])
        saved = Store(self.store.path).load().data["expenses"][0]
        self.assertEqual((saved["amount"], saved["deleted"]), (36000, False))


if __name__ == "__main__":
    unittest.main()
