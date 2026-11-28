"""기준월 포함 3개월, 빈 달도 포함한 평균을 천 원 단위로 올림한다."""
import copy
import contextlib
import io
import json

from helpers import StoreCase
from moim import cli
from moim.features import budget


class SuggestBudgetTest(StoreCase):
    def command(self, *args):
        self.store.save()
        path = self.path("config.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"data": self.store.path}, stream)
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        lines, error = [], io.StringIO()
        with contextlib.redirect_stderr(error):
            code = cli.main(["--config", path, "budget", "suggest", *args],
                            out=lines.append)
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)
        return code, lines, error.getvalue()

    def expense(self, day, amount, deleted=False):
        self.store.data["expenses"].append({
            "id": len(self.store.data["expenses"]) + 1,
            "date": day, "amount": amount, "deleted": deleted})

    def test_three_month_window_includes_endpoints_and_excludes_deleted(self):
        self.expense("2026-08-31", 900000)
        self.expense("2026-09-01", 30000)
        self.expense("2026-10-15", 60000)
        self.expense("2026-11-30", 90000)
        self.expense("2026-11-12", 900000, deleted=True)
        self.expense("2026-12-01", 900000)
        self.assertEqual(budget.suggest_budget(self.store, "2026-11"), 60000)

    def test_average_includes_months_without_expenses(self):
        self.expense("2026-11-01", 9000)
        self.assertEqual(budget.suggest_budget(self.store, "2026-11"), 3000)

    def test_thousand_won_rounding_and_tiny_fraction(self):
        for total, expected in [(0, 0), (1, 1000), (2999, 1000),
                                (3000, 1000), (3001, 2000), (9001, 4000)]:
            with self.subTest(total=total):
                self.store.data["expenses"] = []
                if total:
                    self.expense("2026-11-01", total)
                self.assertEqual(budget.suggest_budget(self.store, "2026-11"), expected)

    def test_year_boundary_and_formatted_amount(self):
        self.expense("2026-10-31", 900000)
        self.expense("2026-11-01", "3,000원")
        self.expense("2026-12-31", "3,000")
        self.expense("2027-01-31", 3000)
        self.assertEqual(budget.suggest_budget(self.store, (2027, 1)), 3000)

    def test_leap_day_and_month_end(self):
        self.expense("2028-01-01", 3000)
        self.expense("2028-02-29", 3000)
        self.expense("2028-03-31", 3000)
        self.assertEqual(budget.suggest_budget(self.store, "2028-03"), 3000)

    def test_invalid_and_date_domain_boundaries(self):
        for month in ("2026-13", "2026-02-01", (2026, True), "0001-01", "0001-02"):
            with self.subTest(month=month), self.assertRaises(ValueError):
                budget.suggest_budget(self.store, month)
        self.assertEqual(budget.suggest_budget(self.store, "0001-03"), 0)
        self.assertEqual(budget.suggest_budget(self.store, "9999-12"), 0)

    def test_query_does_not_change_memory_or_saved_file(self):
        self.expense("2026-11-01", 1000)
        self.store.save()
        before = copy.deepcopy(self.store.data)
        with open(self.store.path, "rb") as stream:
            saved = stream.read()
        budget.suggest_budget(self.store, "2026-11")
        self.assertEqual(self.store.data, before)
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), saved)

    def test_cli_displays_suggestion_without_saving(self):
        self.expense("2026-11-01", 9001)
        self.assertEqual(self.command("--month", "2026-11"),
                         (0, ["기준월 2026-11 다음 달 예산 제안: 4,000원"], ""))

    def test_cli_empty_history_suggests_zero(self):
        self.assertEqual(self.command("--month", "2026-11"),
                         (0, ["기준월 2026-11 다음 달 예산 제안: 0원"], ""))

    def test_cli_invalid_month_returns_one_error_line(self):
        code, lines, error = self.command("--month", "2026-13")
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(len(error.splitlines()), 1)
        self.assertTrue(error.startswith("오류: "))
