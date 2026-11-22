"""실제 CLI에서 파일 저장, 조회의 불변성, 잘못된 인자를 검사한다."""
import json

from helpers import NAMES, StoreCase
from moim import cli


class BudgetCommandsTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.save()
        self.config_path = self.path("config.json")
        with open(self.config_path, "w", encoding="utf-8") as stream:
            json.dump({"data": self.store.path, "budget": {"monthly": 100000}}, stream)

    def run_command(self, *args):
        lines = []
        code = cli.main(["--config", self.config_path, "budget", *args], out=lines.append)
        self.assertEqual(code, 0)
        return lines

    def test_payment_is_saved_and_visible_in_next_command(self):
        lines = self.run_command("pay", "--date", "2026-11-02", "--member", NAMES[1],
                                 "--amount", "20,000", "--memo", "11월 회비")
        self.assertEqual(lines, [f"회비 입금 기록: 2026-11-02 {NAMES[1]} 20,000원"])
        self.store.load()
        self.assertEqual(self.store.data["payments"][0]["memo"], "11월 회비")
        self.assertEqual(self.run_command("balance"), ["통장 잔고: 20,000원"])
        self.assertEqual(self.run_command("balance", "--until", "2026-11-01"),
                         ["통장 잔고: 0원"])

    def test_status_uses_config_and_does_not_save(self):
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        self.assertEqual(self.run_command("status", "--month", "2026-11"),
                         ["2026-11 월 예산: 100,000원", "사용액: 0원",
                          "남은 금액: 100,000원", "예산 이내"])
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)

    def test_status_today_filters_expenses_and_reports_over_budget(self):
        self.store.data["expenses"] = [
            {"id": 1, "date": "2026-11-01", "amount": 100001},
            {"id": 2, "date": "2026-11-30", "amount": 500},
        ]
        self.store.save()
        self.assertEqual(self.run_command("status", "--month", "2026-11",
                                          "--today", "2026-11-01"),
                         ["2026-11 월 예산: 100,000원", "사용액: 100,001원",
                          "남은 금액: -1원", "예산 초과"])

    def test_invalid_payment_does_not_save(self):
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        with self.assertRaises(ValueError):
            self.run_command("pay", "--date", "2026-11-02", "--member", NAMES[0],
                             "--amount", "0")
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)

    def test_parser_requires_month_and_payment_fields(self):
        parser = cli.build_parser()
        for args in [["budget"], ["budget", "status"], ["budget", "pay"]]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                parser.parse_args(args)
            self.assertEqual(error.exception.code, 2)
