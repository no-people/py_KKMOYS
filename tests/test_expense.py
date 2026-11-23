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


class TestAddExpense(StoreCase):
    """features.expenses.add_expense — (지출, 경고 목록), 중복 의심 경고, 검사·확정 기간·이력."""

    NAMES = ["김민수", "이서연", "박지훈"]

    def add(self, date="2026-11-12", payer="김민수", amount="36,000", members=None, **kw):
        from moim.features import expenses
        return expenses.add_expense(self.store, date, payer, amount,
                                    list(members or self.NAMES), **kw)

    def snapshot(self):
        d = self.store.data
        return (json.dumps(d["expenses"]), json.dumps(d["history"]), d["next_id"])

    def test_returns_expense_and_empty_warnings(self):
        e, warnings = self.add(memo="회의 후 저녁")
        self.assertEqual(warnings, [])
        self.assertEqual(e, {
            "id": 1, "date": "2026-11-12", "payer": "김민수", "amount": 36000,
            "members": self.NAMES, "weights": None, "category": None,
            "memo": "회의 후 저녁", "deleted": False, "recurring_id": None,
            "category_fixed": False,
        })
        self.assertIs(self.store.get_expense(1), e)

    def test_duplicate_warning_names_earlier_id_only(self):
        first, _ = self.add()
        second, warnings = self.add(amount=36000)
        self.assertEqual(len(warnings), 1)
        self.assertIn("중복 의심", warnings[0])
        self.assertIn(f"({first['id']}번)", warnings[0])
        self.assertNotIn(str(second["id"]), warnings[0])
        self.assertEqual(len(self.store.data["expenses"]), 2)   # 경고만 하고 추가는 한다

    def test_duplicate_warning_lists_all_ids(self):
        self.add()
        self.add(amount="36,000원")
        _, warnings = self.add(amount=36000)
        self.assertIn("(1, 2번)", warnings[0])

    def test_no_warning_when_any_key_differs(self):
        self.add()
        for kw in ({"date": "2026-11-13"}, {"payer": "이서연"}, {"amount": 36001}):
            _, warnings = self.add(**kw)
            self.assertEqual(warnings, [], kw)

    def test_no_warning_for_deleted_expense(self):
        first, _ = self.add()
        first["deleted"] = True
        _, warnings = self.add()
        self.assertEqual(warnings, [])

    def test_invalid_input_adds_nothing(self):
        from moim.features import expenses
        cases = (("-3000", self.NAMES), ("0", self.NAMES), ("0.4", self.NAMES), ("abc", self.NAMES),
                 ("Infinity", self.NAMES), (3000, []), (3000, ["없는사람"]),
                 (3000, ["김민수", "김민수"]))
        for amount, members in cases:
            before = self.snapshot()
            with self.assertRaises(ValueError, msg=(amount, members)):
                expenses.add_expense(self.store, "2026-11-12", "김민수", amount, members)
            self.assertEqual(self.snapshot(), before, (amount, members))

    def test_invalid_date_raises(self):
        for day in ("2026-11-31", "2026/11/12", "2026-02-29"):
            before = self.snapshot()
            with self.assertRaises(ValueError, msg=day):
                self.add(date=day)
            self.assertEqual(self.snapshot(), before, day)

    def test_leap_day_accepted(self):
        e, _ = self.add(date="2028-02-29")
        self.assertEqual(e["date"], "2028-02-29")

    def test_locked_period_boundary(self):
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        before = self.snapshot()
        for day in ("2026-11-01", "2026-11-30"):   # 시작일·끝일 모두 포함(규약 3)
            with self.assertRaisesRegex(ValueError, f"정산이 확정된 기간입니다: {day}"):
                self.add(date=day)
        self.assertEqual(self.snapshot(), before)
        for day in ("2026-10-31", "2026-12-01"):
            e, _ = self.add(date=day)
            self.assertEqual(e["date"], day)

    def test_before_join_rejected(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "김민수"):   # 가입일 2026-09-01 의 전날
            self.add(date="2026-08-31")
        self.assertEqual(self.snapshot(), before)
        e, _ = self.add(date="2026-09-01")   # 가입일 당일부터 회원
        self.assertEqual(e["date"], "2026-09-01")

    def test_weights_mismatch_adds_nothing(self):
        before = self.snapshot()
        for w in ({"김민수": 1}, {"김민수": 1, "이서연": 1, "박지훈": 1}, {"김민수": 0, "이서연": 1}):
            with self.assertRaises(ValueError, msg=w):
                self.add(members=["김민수", "이서연"], weights=w)
        self.assertEqual(self.snapshot(), before)

    def test_left_member_boundary(self):
        self.store.member("박지훈")["left"] = "2026-11-15"
        e, _ = self.add(date="2026-11-15")   # 탈퇴일 당일까지 회원
        self.assertIn("박지훈", e["members"])
        with self.assertRaisesRegex(ValueError, "박지훈"):
            self.add(date="2026-11-16")
        with self.assertRaisesRegex(ValueError, "박지훈"):   # 낸 사람도 그날 회원이어야 한다
            self.add(date="2026-11-16", payer="박지훈", members=["김민수"])

    def test_history_records_add(self):
        e, _ = self.add()
        h = self.store.data["history"]
        self.assertEqual(len(h), 1)
        self.assertEqual((h[0]["id"], h[0]["action"], h[0]["before"]), (e["id"], "add", None))
        self.assertEqual(h[0]["after"]["amount"], 36000)

    def test_does_not_save(self):
        from moim.common.store import Store
        self.add()
        self.assertEqual(Store(self.store.path).load().data["expenses"], [])

    def test_weights_category_and_date_object(self):
        from datetime import date
        w = {"김민수": 2, "이서연": 1}
        e, _ = self.add(date=date(2026, 11, 12), members=["김민수", "이서연"],
                        weights=w, category="식비")
        self.assertEqual((e["date"], e["weights"], e["category"]), ("2026-11-12", w, "식비"))
        self.assertFalse(e["category_fixed"])
        w["김민수"] = 9
        self.assertEqual(e["weights"]["김민수"], 2)   # 넘긴 dict 를 나중에 고쳐도 지출은 그대로

    def test_payer_not_in_members(self):
        e, _ = self.add(payer="김민수", members=["이서연"], amount="1234.5")
        self.assertEqual((e["payer"], e["members"], e["amount"]), ("김민수", ["이서연"], 1235))


if __name__ == "__main__":
    unittest.main()
