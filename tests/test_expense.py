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

    def test_edit_category_strip_none_and_reject(self):
        from moim.features.expenses import edit_expense
        e = self.put(category="식비")
        edit_expense(self.store, e["id"], category="  장소 ")
        self.assertEqual((e["category"], self.store.data["history"][-1]["after"]["category"]), ("장소", "장소"))
        edit_expense(self.store, e["id"], category=None)
        self.assertIsNone(e["category"])
        for bad in (5, True, ["식비"], 1.0):
            before = self.snapshot()
            with self.assertRaises(ValueError) as cm:
                edit_expense(self.store, e["id"], category=bad)
            self.assertEqual(str(cm.exception), f"분류는 문자열이어야 합니다: {bad!r}")
            self.assertEqual(self.snapshot(), before, repr(bad))

    def test_edit_other_field_keeps_old_category(self):
        from moim.features.expenses import edit_expense
        e = self.put(category="식비")
        e["category"] = 7   # 손으로 고친 옛 자료: 분류를 바꾸지 않으면 검사하지 않고 그대로 둔다
        edit_expense(self.store, e["id"], memo="고침")
        self.assertEqual((e["category"], e["memo"]), (7, "고침"))

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

    def test_restore_revalidates_member(self):
        from moim.features.expenses import delete_expense, restore_expense
        e = self.put("2026-11-20", members=("김민수", "박지훈"))
        delete_expense(self.store, e["id"])
        self.store.member("박지훈")["left"] = "2026-11-15"   # 삭제된 동안 탈퇴
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, f"{e['id']}번 지출을 되살릴 수 없습니다: 그날 회원이 아닙니다: 박지훈"):
            restore_expense(self.store, e["id"])
        self.assertEqual(self.snapshot(), before)   # 삭제 표시·이력 그대로
        self.store.member("박지훈")["left"] = "2026-11-20"   # 탈퇴일 당일 지출이면 되살릴 수 있다
        self.assertFalse(restore_expense(self.store, e["id"])["deleted"])

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


class TestHistoryQuery(StoreCase):
    """history(store, eid=None): 기록 순서, 지출별 거르기, 복사본, 옛 자료·깨진 자료."""

    def setUp(self):
        super().setUp()
        from moim.features import expenses
        self.ex = expenses
        self.e1, _ = expenses.add_expense(self.store, "2026-11-12", "김민수", 36000, ["김민수", "이서연"])
        self.e2, _ = expenses.add_expense(self.store, "2026-11-13", "이서연", 9000, ["이서연", "박지훈"])
        expenses.edit_expense(self.store, 1, amount=30000)
        expenses.delete_expense(self.store, 2)
        expenses.restore_expense(self.store, 2)

    def test_all_in_recorded_order(self):
        items = self.ex.history(self.store)
        self.assertEqual([(h["id"], h["action"]) for h in items],
                         [(1, "add"), (2, "add"), (1, "edit"), (2, "delete"), (2, "restore")])
        for h in items:
            self.assertRegex(h["at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_filter_by_id_shows_what_changed(self):
        items = self.ex.history(self.store, 1)
        self.assertEqual([h["action"] for h in items], ["add", "edit"])
        self.assertIsNone(items[0]["before"])
        self.assertEqual((items[1]["before"]["amount"], items[1]["after"]["amount"]), (36000, 30000))
        self.assertEqual([h["action"] for h in self.ex.history(self.store, "2")], ["add", "delete", "restore"])

    def test_deleted_expense_history_still_shown(self):
        self.ex.delete_expense(self.store, 1)
        self.assertEqual(self.ex.history(self.store, 1)[-1]["action"], "delete")

    def test_returns_copy(self):
        items = self.ex.history(self.store, 1)
        items[1]["before"]["amount"] = 1
        items.clear()
        self.assertEqual(self.store.data["history"][2]["before"]["amount"], 36000)
        self.assertEqual(len(self.store.data["history"]), 5)

    def test_unknown_id_raises(self):
        for eid in (3, 0, -1):
            with self.assertRaises(ValueError):
                self.ex.history(self.store, eid)

    def test_old_data_without_history(self):
        for value in ("missing", None, []):
            if value == "missing":
                self.store.data.pop("history")
            else:
                self.store.data["history"] = value
            self.assertEqual(self.ex.history(self.store), [])
            self.assertEqual(self.ex.history(self.store, 1), [])

    def test_broken_history_raises(self):
        good = self.store.data["history"][0]
        for broken in ("깨짐", {}, "", 0, ["junk", good], [good, None]):
            self.store.data["history"] = broken
            for eid in (None, 1):   # 전체·번호별 모두 같은 오류(Store.record 와 같은 기준)
                with self.assertRaises(ValueError):
                    self.ex.history(self.store, eid)


if __name__ == "__main__":
    unittest.main()
