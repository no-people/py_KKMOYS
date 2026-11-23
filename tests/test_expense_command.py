"""명령 exp — add·list. cli.run(parse_args(...)) 으로 실행한다. 기본 명부: 김민수·이서연·박지훈."""

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
        from moim.features.expenses import delete_expense
        delete_expense(self.store, 1)
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

    # --- 하위 명령 없음
    def test_no_subcommand(self):
        changed, lines = self.cmd()
        self.assertFalse(changed)
        self.assertTrue(lines[0].startswith("하위 명령을 지정하십시오: exp add, list"))


if __name__ == "__main__":
    unittest.main()
