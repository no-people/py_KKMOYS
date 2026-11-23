"""명령 `settle show`(기능 4). 기간 인자, 사람별 표, 잔액 합 검사 줄."""

import unittest
from unittest import mock

from helpers import StoreCase

from moim import cli
from moim.commands import settle as cmd
from moim.features import settle

KIM, LEE, PARK = "김민수", "이서연", "박지훈"


class SettleShowTest(StoreCase):
    def _add(self, date, payer, amount, members=(KIM, LEE, PARK)):
        self.store.data["expenses"].append({
            "id": self.store.new_id(), "date": date, "payer": payer, "amount": amount,
            "members": list(members), "weights": None, "category": None, "memo": "",
            "deleted": False, "recurring_id": None})

    def call(self, *argv):
        lines = []
        args = cli.build_parser().parse_args(["settle", *argv])
        changed = cli.run(args, self.cfg, self.store, lines.append)
        return changed, lines

    def test_month_table(self):
        self._add("2026-11-12", KIM, 9000)
        changed, lines = self.call("show", "--month", "2026-11")
        self.assertFalse(changed)   # 보기만 하므로 저장하지 않는다
        self.assertEqual(lines[0], "정산 기간: 2026-11-01 ~ 2026-11-30")
        self.assertEqual(lines[1].split(), ["이름", "낸", "돈", "부담", "보낸", "송금", "받은", "송금", "잔액", "구분"])
        self.assertEqual(lines[3].split(), [KIM, "9,000", "3,000", "0", "0", "6,000", "받을", "돈"])
        self.assertEqual(lines[4].split(), [LEE, "0", "3,000", "0", "0", "-3,000", "보낼", "돈"])
        self.assertEqual(lines[5].split(), [PARK, "0", "3,000", "0", "0", "-3,000", "보낼", "돈"])
        self.assertEqual(lines[-1], "잔액 합: 0원 (정상)")

    def test_start_end_period(self):
        # 규약 3: 시작일·끝일 포함
        self._add("2026-11-09", KIM, 3000)
        self._add("2026-11-10", KIM, 3000)
        self._add("2026-11-20", LEE, 3000)
        _, lines = self.call("show", "--start", "2026-11-10", "--end", "2026-11-20")
        self.assertEqual(lines[0], "정산 기간: 2026-11-10 ~ 2026-11-20")
        self.assertEqual(lines[3].split()[:2], [KIM, "3,000"])
        self.assertEqual(lines[4].split()[:2], [LEE, "3,000"])

    def test_remainder_shown(self):
        # 규약 2: 10,000 / 3 → 낸 사람 박지훈 3,334
        self._add("2026-11-12", PARK, 10000)
        _, lines = self.call("show", "--month", "2026-11")
        self.assertEqual(lines[5].split()[:3], [PARK, "10,000", "3,334"])
        self.assertEqual(lines[-1], "잔액 합: 0원 (정상)")

    def test_table_shape_spec_6_1(self):
        # 규격 6-1 예와 같은 모양: 머리줄은 왼쪽 정렬, 열마다 - 줄, 숫자 열은 오른쪽 정렬, 한글 2칸
        self.assertEqual(cmd._table(["이름", "낸 돈"], [["김민수", 9000], ["이서연", 6000]], numeric={1}),
                         "이름    낸 돈\n------  -----\n김민수  9,000\n이서연  6,000")

    def test_table_negative_and_wide(self):
        self.assertEqual(cmd._table(["이름", "잔액"], [["김민수", 1234567], ["Al", -5]], numeric={1}),
                         "이름    잔액\n------  ---------\n김민수  1,234,567\nAl             -5")

    def test_empty_period(self):
        _, lines = self.call("show", "--month", "2026-11")
        self.assertEqual(lines, ["정산 기간: 2026-11-01 ~ 2026-11-30", "이 기간에 정산할 지출·송금이 없습니다"])

    def test_nonzero_sum_warning(self):
        rows = {KIM: {"paid": 100, "owed": 0, "sent": 0, "received": 0, "balance": 100}}
        with mock.patch.object(settle, "balances", return_value=rows):
            _, lines = self.call("show", "--month", "2026-11")
        self.assertEqual(lines[-1], "경고: 잔액 합이 0이 아닙니다: 100원 (자료를 확인하십시오)")

    def test_period_required(self):
        with self.assertRaisesRegex(ValueError, "기간을 지정"):
            self.call("show")

    def test_bad_month(self):
        with self.assertRaises(ValueError):
            self.call("show", "--month", "2026-13")

    def test_subcommand_required(self):
        with self.assertRaises((SystemExit, ValueError)):
            cli.build_parser().parse_args(["settle"])

    def test_does_not_change_data(self):
        self._add("2026-11-12", KIM, 9000)
        before = repr(self.store.data)
        self.call("show", "--month", "2026-11")
        self.assertEqual(repr(self.store.data), before)


if __name__ == "__main__":
    unittest.main()
