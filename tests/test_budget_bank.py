"""은행 가져오기: CSV 공통 함수의 반환 계약을 사용해 행 처리·중복·잠금을 검증한다."""
import copy
import json
from unittest.mock import patch

from helpers import NAMES, StoreCase
from moim import cli
from moim.common.store import Store
from moim.features import budget

KIM, LEE, PARK = NAMES


def row(day="2026.11.02", memo=LEE, outgoing="", incoming="20000", time="09:10", balance="20000"):
    return dict(zip(budget.BANK_COLUMNS, [day, time, memo, outgoing, incoming, balance]))


class BankImportTest(StoreCase):
    def run_rows(self, rows):
        with patch.object(budget, "read_csv_rows", return_value=("cp949", list(enumerate(rows, 2)))) as read:
            result = budget.import_bank(self.store, "bank.csv", KIM)
        read.assert_called_once_with("bank.csv", mapping={key: key for key in budget.BANK_COLUMNS})
        return result

    def test_income_expense_date_conversion_and_history(self):
        result = self.run_rows([row(), row("2026.11.03", "회의 후 저녁", "48,000", "", balance="-28000")])
        self.assertEqual(result, {"expenses": [1], "payments": 1, "duplicates": [], "errors": []})
        payment = self.store.data["payments"][0]
        self.assertEqual((payment["date"], payment["member"], payment["source"]), ("2026-11-02", LEE, "bank"))
        expense = self.store.data["expenses"][0]
        self.assertEqual((expense["payer"], expense["members"], expense["amount"]), (KIM, NAMES, 48000))
        self.assertEqual(self.store.data["history"][-1]["action"], "bank")
        self.assertEqual(budget.treasury_balance(self.store), -28000)

    def test_same_file_twice_and_exact_duplicate_line(self):
        rows = [row(), row("2026.11.03", "저녁", "9000", ""), row()]
        self.assertEqual(self.run_rows(rows)["duplicates"], [4])
        before = copy.deepcopy(self.store.data)
        result = self.run_rows(rows)
        self.assertEqual(result, {"expenses": [], "payments": 0, "duplicates": [2, 3, 4], "errors": []})
        self.assertEqual(self.store.data, before)

    def test_manual_income_is_separate_but_repeated_bank_income_is_duplicate(self):
        budget.record_payment(self.store, "2026-11-02", LEE, 20000)
        self.assertEqual(self.run_rows([row()])["payments"], 1)
        self.assertEqual(self.run_rows([row()])["duplicates"], [2])
        self.assertEqual(len(self.store.data["payments"]), 2)

    def test_members_on_leave_day_and_following_day(self):
        self.store.data["members"][2]["left"] = "2026-11-15"
        result = self.run_rows([row("2026.11.15", "저녁", "100", ""),
                                row("2026.11.16", "저녁", "100", "")])
        self.assertFalse(result["errors"])
        self.assertEqual(self.store.data["expenses"][0]["members"], NAMES)
        self.assertEqual(self.store.data["expenses"][1]["members"], [KIM, LEE])

    def test_invalid_lines_are_reported_and_valid_lines_continue(self):
        rows = [row(outgoing="1"), row(incoming="0"), row(incoming="-1"),
                row(day="2026.11.31"), row(time="25:00"), row(memo="없는사람"), row(incoming="2.5")]
        result = self.run_rows(rows)
        self.assertEqual([line for line, _ in result["errors"]], list(range(2, 8)))
        self.assertEqual(result["payments"], 1)
        self.assertEqual(self.store.data["payments"][0]["amount"], 3)
        self.assertEqual(self.store.data["expenses"], [])

    def test_locked_expense_is_rejected_without_consuming_id(self):
        self.store.data["locks"] = [{"start": "2026-11-01", "end": "2026-11-30"}]
        before = copy.deepcopy(self.store.data)
        result = self.run_rows([row(memo="저녁", outgoing="9000", incoming="")])
        self.assertEqual(result["errors"][0][0], 2)
        self.assertIn("확정", result["errors"][0][1])
        self.assertEqual(self.store.data, before)

    def test_null_payments_and_missing_columns(self):
        self.store.data["payments"] = None
        self.assertEqual(self.run_rows([row()])["payments"], 1)
        broken = row(); del broken["잔액"]
        self.assertEqual(self.run_rows([broken])["errors"][0][0], 2)

    def test_same_amount_different_memo_is_not_duplicate(self):
        result = self.run_rows([row(memo="저녁", outgoing="9000", incoming=""),
            row(memo="점심", outgoing="9000", incoming=""),
            row(memo="저녁", outgoing="9000", incoming="", time="10:00")])
        self.assertEqual(result["expenses"], [1, 2])
        self.assertEqual(result["duplicates"], [4])

    def test_inactive_treasurer_is_row_error_and_later_income_continues(self):
        result = self.run_rows([row("2026.08.31", "저녁", "9000", ""), row()])
        self.assertEqual(result["expenses"], [])
        self.assertEqual(result["errors"][0][0], 2)
        self.assertEqual(result["payments"], 1)

    def test_cli_saves_once_and_second_run_does_not_rewrite_file(self):
        self.store.save()
        config_path = self.path("config.json")
        with open(config_path, "w", encoding="utf-8") as stream:
            json.dump({"data": self.store.path, "treasurer": KIM}, stream)
        values = ("utf-8-sig", [(2, row())])
        args = ["--config", config_path, "budget", "import-bank", "bank.csv"]
        lines = []
        original_save = Store.save
        with patch.object(budget, "read_csv_rows", return_value=values), \
                patch.object(Store, "save", autospec=True, side_effect=original_save) as save:
            self.assertEqual(cli.main(args, out=lines.append), 0)
            self.assertEqual(lines, ["은행 가져오기: 지출 0건, 회비 입금 1건"])
            self.assertEqual(save.call_count, 1)
            with open(self.store.path, "rb") as stream:
                before = stream.read()
            lines.clear()
            self.assertEqual(cli.main(args, out=lines.append), 0)
            self.assertEqual(lines, ["은행 가져오기: 지출 0건, 회비 입금 0건", "중복으로 건너뛴 행: 2"])
            self.assertEqual(save.call_count, 1)
            with open(self.store.path, "rb") as stream:
                self.assertEqual(stream.read(), before)
