"""정산 연동 전 계산 계약: 월별 회비 부족액, 읽기 전용."""
import copy
import contextlib
import io
import json

from helpers import NAMES, StoreCase
from moim import cli
from moim.features import budget

KIM, LEE, PARK = NAMES


class DuesDeductionTest(StoreCase):
    def command(self, *args):
        self.store.save()
        path = self.path("config.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"data": self.store.path, "dues": self.cfg["dues"]}, stream)
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        lines, error = [], io.StringIO()
        with contextlib.redirect_stderr(error):
            code = cli.main(["--config", path, "budget", "deduction", *args],
                            out=lines.append)
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)
        return code, lines, error.getvalue()

    def pay(self, name, amount, day="2026-11-02", source="manual"):
        self.store.data.setdefault("payments", []).append({
            "date": day, "member": name, "amount": amount, "source": source})

    def test_partial_full_and_overpayment(self):
        self.pay(KIM, 7000)
        self.pay(KIM, 5000, "2026-11-30", "bank")
        self.pay(LEE, 20000)
        self.pay(PARK, 25000)
        self.assertEqual(budget.dues_deduction(self.store, self.cfg, "2026-11"),
                         {KIM: 8000})

    def test_membership_endpoints_and_roster_order(self):
        self.store.data["members"] = [
            {"name": "말일가입", "joined": "2028-02-29", "left": None},
            {"name": "초일탈퇴", "joined": "2026-09-01", "left": "2028-02-01"},
            {"name": "중간회원", "joined": "2028-02-02", "left": "2028-02-28"}]
        result = budget.dues_deduction(self.store, self.cfg, (2028, 2))
        self.assertEqual(result, {"말일가입": 20000, "초일탈퇴": 20000})
        self.assertEqual(list(result), ["말일가입", "초일탈퇴"])

    def test_other_month_payments_do_not_reduce_this_month(self):
        self.pay(KIM, 20000, "2026-10-31")
        self.pay(KIM, 20000, "2026-12-01")
        self.assertEqual(budget.dues_deduction(self.store, self.cfg, "2026-11"),
                         {KIM: 20000, LEE: 20000, PARK: 20000})

    def test_empty_old_payments_and_zero_due(self):
        for old in (None, []):
            self.store.data["payments"] = old
            self.assertEqual(len(budget.dues_deduction(self.store, self.cfg, "2026-11")), 3)
            self.assertEqual(self.store.data["payments"], old)
        self.cfg["dues"]["monthly"] = 0
        self.assertEqual(budget.dues_deduction(self.store, self.cfg, "2026-11"), {})
        self.store.data["members"] = []
        self.assertEqual(budget.dues_deduction(self.store, self.cfg, "2026-11"), {})

    def test_invalid_month_and_missing_or_invalid_due(self):
        for month in ("2026-13", (True, 11)):
            with self.subTest(month=month), self.assertRaises(ValueError):
                budget.dues_deduction(self.store, self.cfg, month)
        for cfg in ({}, {"dues": {"monthly": None}}, {"dues": {"monthly": -1}}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                budget.dues_deduction(self.store, cfg, "2026-11")

    def test_store_configuration_and_file_are_unchanged(self):
        self.pay(KIM, 1000)
        self.store.save()
        original = copy.deepcopy(self.store.data), copy.deepcopy(self.cfg)
        with open(self.store.path, "rb") as stream:
            saved = stream.read()
        budget.dues_deduction(self.store, self.cfg, "2026-11")
        self.assertEqual((self.store.data, self.cfg), original)
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), saved)

    def test_cli_displays_deduction_without_changing_settlement_data(self):
        self.pay(KIM, 19000)
        self.pay(LEE, 20000)
        self.pay(PARK, 25000)
        before = copy.deepcopy(self.store.data)
        self.assertEqual(self.command("--month", "2026-11"),
                         (0, [f"{KIM}: 회비 차감 예정액 1,000원"], ""))
        self.assertEqual(self.store.data, before)

    def test_cli_no_deduction(self):
        self.cfg["dues"]["monthly"] = 0
        self.assertEqual(self.command("--month", "2026-11"),
                         (0, ["회비 차감 대상이 없습니다."], ""))

    def test_cli_invalid_month_returns_one_error_line(self):
        code, lines, error = self.command("--month", "2026-13")
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(len(error.splitlines()), 1)
        self.assertTrue(error.startswith("오류: "))
