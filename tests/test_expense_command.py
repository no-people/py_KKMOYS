"""명령 exp — add·list·edit·delete·restore·history·import-lines·undo. cli.run(parse_args(...)) 으로 실행한다. 기본 명부: 김민수·이서연·박지훈."""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import StoreCase  # noqa: E402


class TestExpenseCommand(StoreCase):

    def cmd(self, *argv):
        from moim import cli
        lines = []
        changed = cli.run(cli.build_parser().parse_args(["exp", *argv]), self.cfg, self.store, out=lines.append)
        return changed, lines

    def add(self, date="2026-11-12", payer="김민수", amount="36,000", members="김민수;이서연;박지훈", *opts):
        return self.cmd("add", date, payer, amount, members, *opts)

    def expenses(self):
        return self.store.data["expenses"]

    # --- add
    def test_add(self):
        changed, lines = self.add("2026-11-12", "김민수", "36,000", "김민수; 이서연;박지훈",
                                  "--memo", "회의 후 저녁", "--category", "식비")
        self.assertEqual((changed, lines), (True, ["지출 추가 1번: 2026-11-12 김민수 36,000원 (3명)"]))
        e = self.expenses()[0]
        self.assertEqual((e["members"], e["memo"], e["category"], e["weights"], e["deleted"]),
                         (["김민수", "이서연", "박지훈"], "회의 후 저녁", "식비", None, False))
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["add"])

    def test_add_weights(self):
        self.add("2026-11-12", "김민수", "30000", "김민수;이서연", "--weights", "김민수=2; 이서연=1")
        self.assertEqual(self.expenses()[0]["weights"], {"김민수": 2, "이서연": 1})

    def test_add_duplicate_warning(self):
        self.add()
        changed, lines = self.add()
        self.assertTrue(changed)
        self.assertEqual(lines[1], "경고: 중복 의심: 같은 날·같은 사람·같은 금액 지출이 있습니다 (1번)")
        self.assertEqual(len(self.expenses()), 2)   # 경고만 하고 추가는 한다

    def test_add_bad_weights_korean_error(self):
        for text in ("김민수2", "김민수=두배", "김민수=2;"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError) as cm:
                    self.add("2026-11-12", "김민수", "1000", "김민수;이서연", "--weights", text)
                self.assertIn("비율 형식이 잘못되었습니다", str(cm.exception))
        self.assertEqual(self.expenses(), [])

    def test_add_rejected_adds_nothing(self):
        for args in (("2026-11-12", "김민수", "0", "김민수"), ("2026-11-12", "김민수", "1000", ""),
                     ("2026-11-31", "김민수", "1000", "김민수"), ("2026-11-12", "없는사람", "1000", "김민수")):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    self.add(*args)
        self.assertEqual((self.expenses(), self.store.data["history"]), ([], []))

    def test_add_locked_rejected(self):
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        for day in ("2026-11-01", "2026-11-30"):
            with self.subTest(day=day):
                with self.assertRaises(ValueError) as cm:
                    self.add(day, "김민수", "1000", "김민수")
                self.assertEqual(str(cm.exception), f"정산이 확정된 기간입니다: {day}")
        self.assertEqual((self.expenses(), self.store.data["history"]), ([], []))
        self.assertTrue(self.add("2026-12-01", "김민수", "1000", "김민수")[0])

    # --- list
    def test_list_empty(self):
        self.assertEqual(self.cmd("list"), (False, ["지출이 없습니다"]))

    def test_list_order_and_total(self):
        self.add("2026-11-12", "김민수", "36000")
        self.add("2026-11-10", "이서연", "5000", "이서연;박지훈", "--memo", "커피")
        self.add("2026-11-11", "박지훈", "5000", "박지훈")
        changed, lines = self.cmd("list", "--order", "amount")
        self.assertFalse(changed)
        self.assertEqual(lines[0].split(), ["번호", "날짜", "낸", "사람", "금액", "참여자", "분류", "메모"])
        self.assertEqual([ln.split()[0] for ln in lines[1:4]], ["2", "3", "1"])   # 같은 금액이면 번호순
        self.assertEqual(lines[1].split(), ["2", "2026-11-10", "이서연", "5,000", "이서연;박지훈", "미분류", "커피"])
        self.assertEqual(lines[-1], "모두 3건, 합계 46,000원")
        self.assertEqual([ln.split()[0] for ln in self.cmd("list", "--order", "date")[1][1:4]], ["2", "3", "1"])

    def test_list_bad_order(self):
        with self.assertRaises(ValueError):
            self.cmd("list", "--order", "payer")

    def test_list_shows_weights(self):
        self.add("2026-11-12", "김민수", "30000", "김민수;이서연", "--weights", "김민수=2;이서연=1")
        self.assertIn("김민수=2;이서연=1", self.cmd("list")[1][1].split())

    def test_list_deleted_hidden_unless_all(self):
        self.add("2026-11-12", "김민수", "36000")
        self.add("2026-11-13", "이서연", "1000", "이서연")
        self.cmd("delete", "1")
        _, lines = self.cmd("list")
        self.assertEqual([ln.split()[0] for ln in lines[1:-1]], ["2"])
        self.assertEqual(lines[-1], "모두 1건, 합계 1,000원")
        _, lines = self.cmd("list", "--all")
        self.assertEqual(lines[0].split()[-1], "상태")
        self.assertEqual(lines[1].split()[-1], "삭제")
        self.assertEqual(lines[-1], "모두 2건, 합계(삭제 1건 제외) 1,000원")

    def test_list_same_date_by_id(self):
        self.add("2026-11-12", "김민수", "3000", "김민수")
        self.add("2026-11-11", "김민수", "2000", "김민수")
        self.add("2026-11-12", "이서연", "1000", "이서연")
        _, lines = self.cmd("list", "--order", "date")
        self.assertEqual([ln.split()[0] for ln in lines[1:-1]], ["2", "1", "3"])

    def test_list_period_with_all(self):
        from moim.features.expenses import delete_expense
        self.add("2026-11-12", "김민수", "1000", "김민수")
        self.add("2026-11-13", "김민수", "2000", "김민수")
        self.add("2026-12-01", "김민수", "4000", "김민수")
        delete_expense(self.store, 2)
        delete_expense(self.store, 3)
        _, lines = self.cmd("list", "--all", "--month", "2026-11")
        self.assertEqual([(ln.split()[0], ln.split()[-1]) for ln in lines[1:-1]], [("1", "미분류"), ("2", "삭제")])
        self.assertEqual(lines[-1], "모두 2건, 합계(삭제 1건 제외) 1,000원")

    def test_list_old_data_without_new_keys(self):
        # history·deleted 등을 넣기 전 자료 파일의 지출: weights·category·memo·deleted 키가 없다
        self.store.data["expenses"].append(
            {"id": 1, "date": "2026-11-12", "payer": "김민수", "amount": 5000, "members": ["김민수", "이서연"]})
        _, lines = self.cmd("list", "--all")
        self.assertEqual(lines[1].split(), ["1", "2026-11-12", "김민수", "5,000", "김민수;이서연", "미분류"])
        self.assertEqual(lines[-1], "모두 1건, 합계 5,000원")

    def test_list_period(self):
        self.add("2026-10-31", "김민수", "1000", "김민수")
        self.add("2026-11-01", "김민수", "2000", "김민수")
        self.add("2026-11-30", "김민수", "3000", "김민수")
        self.add("2026-12-01", "김민수", "4000", "김민수")
        _, lines = self.cmd("list", "--month", "2026-11")
        self.assertEqual([ln.split()[0] for ln in lines[1:-1]], ["2", "3"])   # 1일·말일 포함
        _, lines = self.cmd("list", "--start", "2026-10-31", "--end", "2026-11-01")
        self.assertEqual(lines[-1], "모두 2건, 합계 3,000원")
        _, lines = self.cmd("list", "--month", "2027-01")
        self.assertEqual(lines, ["지출이 없습니다"])
        with self.assertRaises(ValueError):
            self.cmd("list", "--start", "2026-11-01")   # 끝일 없음
        with self.assertRaises(ValueError):
            self.cmd("list", "--end", "2026-11-30")   # 시작일 없음

    # --- edit
    def test_edit_shows_changes(self):
        self.add("2026-11-12", "김민수", "36000", "김민수;이서연", "--memo", "저녁")
        changed, lines = self.cmd("edit", "1", "--amount", "30,000", "--memo", "점심", "--payer", "김민수")
        self.assertTrue(changed)
        self.assertEqual(lines, ["지출 수정 1번", "  금액: 36,000원 → 30,000원", "  메모: 저녁 → 점심"])
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["add", "edit"])

    def test_edit_members_weights_equal(self):
        self.add("2026-11-12", "김민수", "30000", "김민수;이서연")
        _, lines = self.cmd("edit", "1", "--members", "김민수;박지훈", "--weights", "김민수=2;박지훈=1")
        self.assertEqual(lines[1:], ["  참여자: 김민수;이서연 → 김민수;박지훈",
                                     "  비율: 없음(똑같이 나눔) → 김민수=2;박지훈=1"])
        _, lines = self.cmd("edit", "1", "--equal")
        self.assertEqual(lines[1:], ["  비율: 김민수=2;박지훈=1 → 없음(똑같이 나눔)"])
        self.assertIsNone(self.expenses()[0]["weights"])

    def test_edit_category_and_date(self):
        self.add("2026-11-12", "김민수", "1000", "김민수")
        _, lines = self.cmd("edit", "1", "--category", "식비", "--date", "2026-11-13")
        self.assertEqual(lines[1:], ["  날짜: 2026-11-12 → 2026-11-13", "  분류: - → 식비"])

    def test_edit_same_value(self):
        self.add("2026-11-12", "김민수", "1000", "김민수", "--memo", "저녁")
        self.assertEqual(self.cmd("edit", "1", "--memo", "저녁")[1], ["지출 수정 1번", "  바뀐 항목 없음"])

    def test_edit_duplicate_warning(self):
        self.add("2026-11-12", "김민수", "1000", "김민수")
        self.add("2026-11-12", "김민수", "2000", "김민수")
        _, lines = self.cmd("edit", "2", "--amount", "1000")
        self.assertEqual(lines[-1], "경고: 중복 의심: 같은 날·같은 사람·같은 금액 지출이 있습니다 (1번)")

    def test_edit_errors_change_nothing(self):
        self.add("2026-11-12", "김민수", "1000", "김민수")
        before = copy.deepcopy(self.expenses())
        for argv in (("edit", "1"), ("edit", "9", "--memo", "x"), ("edit", "1", "--amount", "0"),
                     ("edit", "1", "--weights", "김민수"), ("edit", "1", "--weights", " ")):
            with self.subTest(argv=argv):
                with self.assertRaises(ValueError):
                    self.cmd(*argv)
        self.assertEqual(self.expenses(), before)
        self.assertEqual(len(self.store.data["history"]), 1)

    def test_edit_old_data_no_fake_change(self):
        self.store.data["expenses"].append(
            {"id": 1, "date": "2026-11-12", "payer": "김민수", "amount": 1000, "members": ["김민수"]})
        self.store.data["next_id"] = 2
        self.assertEqual(self.cmd("edit", "1", "--amount", "2000")[1], ["지출 수정 1번", "  금액: 1,000원 → 2,000원"])

    def test_locked_edit_delete_keep_data(self):
        self.add("2026-11-30", "김민수", "1000", "김민수")
        self.add("2026-12-01", "김민수", "2000", "김민수")
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        before = copy.deepcopy(self.store.data)
        for argv in (("edit", "1", "--memo", "x"), ("delete", "1"), ("edit", "2", "--date", "2026-11-30")):
            with self.subTest(argv=argv):
                with self.assertRaises(ValueError) as cm:
                    self.cmd(*argv)
                self.assertEqual(str(cm.exception), "정산이 확정된 기간입니다: 2026-11-30")
        self.assertEqual(self.store.data, before)

    def test_edit_deleted_rejected(self):
        self.add()
        self.cmd("delete", "1")
        before = copy.deepcopy(self.store.data)
        with self.assertRaises(ValueError):
            self.cmd("edit", "1", "--memo", "x")
        self.assertEqual(self.store.data, before)

    def test_eid_must_be_int(self):
        from moim.cli import UsageError
        for argv in (("edit", "abc", "--memo", "x"), ("delete", "1.5"), ("restore", "")):
            with self.subTest(argv=argv):
                with self.assertRaises(UsageError) as cm:
                    self.cmd(*argv)
                self.assertIn("명령 형식이 잘못되었습니다", str(cm.exception))

    def test_weights_and_equal_together_rejected(self):
        from moim.cli import UsageError
        with self.assertRaises(UsageError):
            self.cmd("edit", "1", "--weights", "김민수=1", "--equal")

    # --- delete·restore
    def test_delete_restore(self):
        self.add()
        changed, lines = self.cmd("delete", "1")
        self.assertEqual((changed, lines),
                         (True, ["지출 삭제 1번: 2026-11-12 김민수 36,000원 (3명) (삭제 표시만, exp restore 1 로 되살림)"]))
        self.assertTrue(self.expenses()[0]["deleted"])
        changed, lines = self.cmd("restore", "1")
        self.assertEqual((changed, lines), (True, ["지출 되살림 1번: 2026-11-12 김민수 36,000원 (3명)"]))
        self.assertFalse(self.expenses()[0]["deleted"])
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["add", "delete", "restore"])

    def test_delete_twice_and_locked(self):
        self.add()
        self.cmd("delete", "1")
        with self.assertRaises(ValueError):
            self.cmd("delete", "1")
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        with self.assertRaises(ValueError) as cm:
            self.cmd("restore", "1")
        self.assertEqual(str(cm.exception), "정산이 확정된 기간입니다: 2026-11-12")
        self.assertTrue(self.expenses()[0]["deleted"])

    # --- history
    def test_history_table(self):
        self.add("2026-11-12", "김민수", "36,000", "김민수;이서연", "--memo", "저녁")
        self.cmd("edit", "1", "--amount", "30000", "--memo", "회의 후 저녁")
        self.cmd("delete", "1")
        changed, lines = self.cmd("history")
        self.assertFalse(changed)
        rows = lines[0].splitlines()   # 표는 한 번에 출력
        self.assertEqual(rows[0].split(), ["시각", "번호", "동작", "바뀐", "내용"])
        self.assertTrue(set(rows[1]) <= {"-", " "})   # textfmt.table 구분선
        self.assertIn("추가  새 지출: 2026-11-12 김민수 36,000원 (2명)", rows[2])
        self.assertIn("수정  금액: 36,000원 → 30,000원; 메모: 저녁 → 회의 후 저녁", rows[3])
        self.assertIn("삭제  삭제: 아니오 → 예", rows[4])
        self.assertEqual(lines[-1], "모두 3건")

    def test_history_by_id(self):
        self.add()
        self.add("2026-11-13", "이서연", "9000", "이서연;박지훈")
        self.cmd("edit", "2", "--members", "이서연")
        changed, lines = self.cmd("history", "2")
        rows = lines[0].splitlines()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r.split()[2] == "2" for r in rows[2:]))
        self.assertIn("참여자: 이서연;박지훈 → 이서연", rows[3])
        self.assertEqual(lines[-1], "모두 2건")

    def test_history_empty_and_same_value_edit(self):
        self.assertEqual(self.cmd("history"), (False, ["이력이 없습니다"]))
        self.add()
        self.cmd("edit", "1", "--memo", "")
        self.assertIn("수정  바뀐 항목 없음", self.cmd("history", "1")[1][0])

    def test_history_other_actions(self):
        from moim.common import ledger
        self.add()
        self.cmd("delete", "1")
        self.cmd("restore", "1")
        ledger.insert(self.store, "2026-11-13", "이서연", 5000, ["이서연"], action="bank")
        self.store.data["history"].append({"id": 2, "action": "edit", "at": "2026-11-28 10:00:00",
                                           "before": {"id": 2}, "after": {"id": 2, "category_fixed": True}})
        self.store.data["history"].append({"id": 2, "action": "add", "at": "2026-11-28 10:00:01",
                                           "before": None, "after": {"id": 2}})   # 키가 빠진 자료
        rows = self.cmd("history")[1][0].splitlines()
        self.assertIn("되살림  삭제: 예 → 아니오", rows[4])
        self.assertIn("은행    새 지출: 2026-11-13 이서연 5,000원 (1명)", rows[5])
        self.assertIn("분류 고정: 아니오 → 예", rows[6])
        self.assertTrue(rows[7].endswith("추가    -"))

    def test_history_unknown_id_and_old_data(self):
        from moim import cli
        self.add()
        with self.assertRaises(ValueError):
            self.cmd("history", "9")
        self.store.data["history"] = None   # 옛 자료
        self.assertEqual(self.cmd("history", "1"), (False, ["이력이 없습니다"]))
        with self.assertRaises(cli.UsageError):
            cli.build_parser().parse_args(["exp", "history", "x"])

    # --- import-lines
    def write(self, text):
        p = self.path("lines.csv")
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def test_import_lines(self):
        self.add("2026-11-12", "김민수", "36000", "김민수")
        p = self.write("# 주석\n2026-11-12,김민수,36000,김민수;이서연,저녁\n"
                       "2026-11-31,김민수,1000,김민수\n\n2026-11-13,이서연,9000,이서연;박지훈\n")
        changed, lines = self.cmd("import-lines", p)
        self.assertTrue(changed)
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "지출 여러 줄 입력: 2건 추가 (2~3번), 잘못된 줄 1개")
        self.assertRegex(lines[1], r"^  3번째 줄 건너뜀: .*2026-11-31")
        self.assertEqual(lines[2], "경고: 2번째 줄: 중복 의심: 같은 날·같은 사람·같은 금액 지출이 있습니다 (1번)")
        self.assertEqual([e["memo"] for e in self.expenses()], ["", "저녁", ""])

    def test_import_lines_nothing_added(self):
        changed, lines = self.cmd("import-lines", self.write("2026-11-12,최유진,1000,최유진\n"))
        self.assertFalse(changed)
        self.assertEqual(lines[0], "지출 여러 줄 입력: 0건 추가, 잘못된 줄 1개")
        self.assertEqual(self.expenses(), [])

    def test_import_lines_cli_missing_file(self):
        import contextlib
        import io
        import json
        from moim import cli
        cfg = self.path("c.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path}, f)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["--config", cfg, "exp", "import-lines", self.path("없음.csv")], out=lambda s: None)
        self.assertEqual(code, 1)
        self.assertIn("파일이 없습니다", err.getvalue())

    # --- undo
    def test_undo(self):
        self.add("2026-11-12", "김민수", "36,000", "김민수;이서연", "--memo", "저녁")
        self.cmd("edit", "1", "--amount", "30000", "--weights", "김민수=2;이서연=1")
        changed, lines = self.cmd("undo", "1")
        self.assertTrue(changed)
        self.assertEqual(lines, ["지출 되돌림 1번 (가장 최근 수정 이전으로)",
                                 "  금액: 30,000원 → 36,000원",
                                 "  비율: 김민수=2;이서연=1 → 없음(똑같이 나눔)"])
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["add", "edit", "undo"])

    def test_undo_rejected(self):
        self.add()
        with self.assertRaisesRegex(ValueError, "되돌릴 수정이 없습니다: 1번"):
            self.cmd("undo", "1")
        self.assertEqual([h["action"] for h in self.store.data["history"]], ["add"])

    def test_history_undo_import_recurring_weights_labels(self):
        from moim.common import ledger
        self.add("2026-11-12", "김민수", "36000", "김민수;이서연")
        self.cmd("edit", "1", "--weights", "김민수=2;이서연=1")
        self.cmd("undo", "1")
        ledger.insert(self.store, "2026-11-13", "이서연", 5000, ["이서연"], action="import")
        ledger.insert(self.store, "2026-11-14", "박지훈", 7000, ["박지훈"], recurring_id=1, action="recurring")
        rows = self.cmd("history")[1][0].splitlines()
        self.assertIn("수정      비율: 없음(똑같이 나눔) → 김민수=2;이서연=1", rows[3])
        self.assertIn("되돌림    비율: 김민수=2;이서연=1 → 없음(똑같이 나눔)", rows[4])
        self.assertIn("가져오기  새 지출: 2026-11-13 이서연 5,000원 (1명)", rows[5])
        self.assertIn("반복      새 지출: 2026-11-14 박지훈 7,000원 (1명)", rows[6])

    def test_history_broken_values_show_dash(self):
        self.add()
        for before, after in (({"weights": [1]}, {"weights": {"김민수": 1}}),
                              ({"members": 5}, {"members": ["김민수"]}),
                              ({"amount": "abc"}, {"amount": 1000})):
            self.store.data["history"].append({"id": 1, "action": "edit", "at": "2026-11-28 10:00:00",
                                               "before": before, "after": after})
        changed, lines = self.cmd("history", "1")   # 트레이스백 없이 표 전체가 나온다
        rows = lines[0].splitlines()
        self.assertEqual(len(rows), 6)
        self.assertIn("비율: - → 김민수=1", rows[3])
        self.assertIn("참여자: - → 김민수", rows[4])
        self.assertIn("금액: - → 1,000원", rows[5])

    # --- 하위 명령 없음
    def test_no_subcommand(self):
        changed, lines = self.cmd()
        self.assertFalse(changed)
        self.assertTrue(lines[0].startswith("하위 명령을 지정하십시오: exp add, list, edit, delete, restore, history, import-lines, undo"))


if __name__ == "__main__":
    unittest.main()
