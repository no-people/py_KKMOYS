"""기능 1(지출 입력·관리) 테스트 — Store.record, history·deleted 자료 항목 경계값 포함."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import StoreCase  # noqa: E402


class TestMembers(StoreCase):
    """add_member·leave_member·list_members 와 member 명령. 기본 명부: 김민수·이서연·박지훈(2026-09-01 가입)."""

    def roster(self):
        return json.dumps(self.store.data["members"], ensure_ascii=False)

    def put(self, date, payer="김민수", members=("김민수", "박지훈"), amount=1000):
        from moim.common import ledger
        return ledger.insert(self.store, date, payer, amount, list(members))

    # --- add_member
    def test_add_appends_in_order(self):
        from datetime import date
        from moim.features.expenses import add_member
        m = add_member(self.store, "  최유진 ", date(2026, 11, 1))
        self.assertEqual(m, {"name": "최유진", "joined": "2026-11-01", "left": None})
        self.assertIs(self.store.data["members"][-1], m)
        self.assertIs(self.store.member("최유진"), m)

    def test_add_rejects_and_keeps_roster(self):
        from moim.features.expenses import add_member
        cases = (("", "2026-11-01"), ("   ", "2026-11-01"), (None, "2026-11-01"), (7, "2026-11-01"),
                 ("최,유진", "2026-11-01"), ("최;유진", "2026-11-01"), ("최=유진", "2026-11-01"),
                 ("#최유진", "2026-11-01"),   # 명부 파일에서 주석 줄이 된다
                 ("김민수", "2026-11-01"), (" 김민수", "2026-11-01"),   # 이미 있음(공백 정리 뒤 같은 이름)
                 ("최유진", "2026-11-31"), ("최유진", "2026/11/01"), ("최유진", "2026-02-29"))
        for name, joined in cases:
            before = self.roster()
            with self.assertRaises(ValueError, msg=(name, joined)):
                add_member(self.store, name, joined)
            self.assertEqual(self.roster(), before, (name, joined))

    def test_add_left_member_again_rejected(self):
        from moim.features.expenses import add_member, leave_member
        leave_member(self.store, "박지훈", "2026-11-15")
        with self.assertRaisesRegex(ValueError, "이미 명부에 있는"):
            add_member(self.store, "박지훈", "2026-12-01")

    def test_added_member_active_from_joined_day(self):
        from moim.common.queries import is_member_active
        from moim.features.expenses import add_member
        add_member(self.store, "최유진", "2028-02-29")   # 윤년
        self.assertFalse(is_member_active(self.store, "최유진", "2028-02-28"))
        self.assertTrue(is_member_active(self.store, "최유진", "2028-02-29"))

    # --- leave_member
    def test_leave_sets_left_and_active_until_that_day(self):
        from moim.common.queries import is_member_active
        from moim.features.expenses import leave_member
        m = leave_member(self.store, "박지훈", "2026-11-15")
        self.assertEqual(m["left"], "2026-11-15")
        self.assertIs(self.store.member("박지훈"), m)
        self.assertTrue(is_member_active(self.store, "박지훈", "2026-11-15"))   # 규약 4: 당일까지
        self.assertFalse(is_member_active(self.store, "박지훈", "2026-11-16"))

    def test_leave_on_joined_day_ok_before_rejected(self):
        from moim.features.expenses import leave_member
        with self.assertRaisesRegex(ValueError, "가입일"):
            leave_member(self.store, "이서연", "2026-08-31")
        self.assertIsNone(self.store.member("이서연")["left"])
        self.assertEqual(leave_member(self.store, "이서연", "2026-09-01")["left"], "2026-09-01")

    def test_leave_rejects_and_keeps_roster(self):
        from moim.features.expenses import leave_member
        leave_member(self.store, "박지훈", "2026-11-15")
        for name, left in (("없는사람", "2026-11-15"), ("박지훈", "2026-11-20"),   # 이미 탈퇴
                           ("이서연", "2026-11-31"), ("이서연", "")):
            before = self.roster()
            with self.assertRaises(ValueError, msg=(name, left)):
                leave_member(self.store, name, left)
            self.assertEqual(self.roster(), before, (name, left))

    def test_leave_blocked_by_later_expense(self):
        from moim.features.expenses import leave_member
        self.put("2026-11-15")                                  # 탈퇴일 당일 지출은 있어도 된다
        a = self.put("2026-11-16")                              # 참여자로 들어간 다음 날 지출
        b = self.put("2026-11-20", payer="박지훈", members=["김민수"])   # 낸 사람인 지출
        with self.assertRaisesRegex(ValueError, f"{a['id']}, {b['id']}번"):
            leave_member(self.store, "박지훈", "2026-11-15")
        self.assertIsNone(self.store.member("박지훈")["left"])
        a["deleted"] = b["deleted"] = True                     # 삭제 표시 지출은 보지 않는다
        self.assertEqual(leave_member(self.store, "박지훈", "2026-11-15")["left"], "2026-11-15")

    def test_leave_name_spaces_and_month_end(self):
        from moim.common.queries import is_member_active
        from moim.features.expenses import leave_member
        self.assertEqual(leave_member(self.store, " 박지훈 ", "2026-10-31")["left"], "2026-10-31")
        self.assertTrue(is_member_active(self.store, "박지훈", "2026-10-31"))   # 말일까지 회원
        self.assertFalse(is_member_active(self.store, "박지훈", "2026-11-01"))

    def test_leave_with_broken_expense_members_keeps_roster(self):
        from moim.features.expenses import leave_member
        self.put("2026-11-20")["members"] = None   # 깨진 자료: TypeError 대신 그냥 건너뜀
        self.put("2026-11-21", payer="박지훈", members=["김민수"])
        with self.assertRaisesRegex(ValueError, "탈퇴일 뒤"):
            leave_member(self.store, "박지훈", "2026-11-15")
        self.assertIsNone(self.store.member("박지훈")["left"])

    def test_leave_not_blocked_by_others_expense(self):
        from moim.features.expenses import leave_member
        self.put("2026-11-20", payer="김민수", members=["김민수", "이서연"])
        self.assertEqual(leave_member(self.store, "박지훈", "2026-11-15")["left"], "2026-11-15")

    # --- list_members
    def test_list_order_and_copy(self):
        from moim.features.expenses import add_member, leave_member, list_members
        add_member(self.store, "최유진", "2026-11-01")
        leave_member(self.store, "박지훈", "2026-11-15")
        got = list_members(self.store)
        self.assertEqual([m["name"] for m in got], ["김민수", "이서연", "박지훈", "최유진"])
        self.assertEqual(got[2], {"name": "박지훈", "joined": "2026-09-01", "left": "2026-11-15"})
        got[0]["name"] = "바뀜"
        self.assertEqual(self.store.data["members"][0]["name"], "김민수")   # 복사본

    def test_list_old_member_without_left(self):
        from moim.features.expenses import list_members
        del self.store.data["members"][0]["left"]   # left 키 없는 옛 자료
        self.assertIsNone(list_members(self.store)[0]["left"])

    def test_does_not_save(self):
        from moim.common.store import Store
        from moim.features.expenses import add_member, leave_member
        add_member(self.store, "최유진", "2026-11-01")
        leave_member(self.store, "박지훈", "2026-11-15")
        self.assertEqual(Store(self.store.path).load().data["members"], [])
        self.assertEqual(self.store.data["history"], [])   # 이력은 지출 변경만 남긴다

    # --- member 명령
    def cmd(self, *argv):
        from moim import cli
        lines = []
        changed = cli.run(cli.build_parser().parse_args(list(argv)), self.cfg, self.store, out=lines.append)
        return changed, lines

    def test_command_add_leave_list(self):
        changed, lines = self.cmd("member", "add", "최유진", "2026-11-01")
        self.assertEqual((changed, lines), (True, ["명부 추가: 최유진 (가입일 2026-11-01)"]))
        changed, lines = self.cmd("member", "leave", "박지훈", "2026-11-15")
        self.assertEqual((changed, lines), (True, ["탈퇴 기록: 박지훈 (탈퇴일 2026-11-15, 그날까지 회원)"]))
        changed, lines = self.cmd("member", "list")
        self.assertFalse(changed)
        self.assertEqual(lines[0].split(), ["이름", "가입일", "탈퇴일"])
        self.assertEqual(lines[3].split(), ["박지훈", "2026-09-01", "2026-11-15"])
        self.assertEqual(lines[4].split(), ["최유진", "2026-11-01", "-"])
        self.assertEqual(lines[-1], "모두 4명")

    def test_command_error_raises_and_not_changed(self):
        before = self.roster()
        with self.assertRaises(ValueError):
            self.cmd("member", "add", "김민수", "2026-11-01")
        self.assertEqual(self.roster(), before)

    def test_command_list_empty(self):
        self.store.data["members"] = []
        self.assertEqual(self.cmd("member", "list"), (False, ["명부가 비어 있습니다"]))


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


if __name__ == "__main__":
    unittest.main()
