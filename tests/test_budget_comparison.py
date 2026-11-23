"""선택 기능: 전체 행은 월 예산, 차이는 예산-실제, 삭제 제외와 지출 합계 일치."""
import copy
import json
from unittest.mock import patch

from helpers import StoreCase
from moim import cli
from moim.common import textfmt
from moim.common.rules import UNCATEGORIZED
from moim.features import budget


class BudgetComparisonTest(StoreCase):
    def add(self, day, amount, category, deleted=False):
        self.store.data["expenses"].append({"id": len(self.store.data["expenses"]) + 1,
            "date": day, "amount": amount, "category": category, "deleted": deleted})

    def test_rows_differences_and_monthly_budget_total(self):
        self.cfg["budget"] = {"monthly": 100000, "by_category": {"식비": 50000, "교통": 10000}}
        self.add("2026-11-01", 30000, " 식비 ")
        self.add("2026-11-30", 15000, "교통")
        self.add("2026-11-15", 500, None)
        self.assertEqual(budget.budget_table(self.store, self.cfg, "2026-11"), [
            ("식비", 50000, 30000, 20000), ("교통", 10000, 15000, -5000),
            (UNCATEGORIZED, 0, 500, -500), ("전체", 100000, 45500, 54500)])

    def test_excludes_other_months_and_deleted_and_preserves_zero_spend(self):
        self.add("2026-10-31", 10000, "식비")
        self.add("2026-11-01", 200, "식비")
        self.add("2026-11-30", 300, "식비")
        self.add("2026-12-01", 20000, "식비")
        self.add("2026-11-15", 30000, "식비", deleted=True)
        self.cfg["budget"]["by_category"]["교통"] = 10000
        rows = budget.budget_table(self.store, self.cfg, (2026, 11))
        self.assertEqual(rows, [("식비", 50000, 500, 49500), ("교통", 10000, 0, 10000),
                                ("전체", 100000, 500, 99500)])
        self.assertEqual(sum(row[2] for row in rows[:-1]), rows[-1][2])

    def test_empty_categories_still_have_monthly_total(self):
        self.cfg["budget"]["by_category"] = {}
        self.assertEqual(budget.budget_table(self.store, self.cfg, "2026-11"),
                         [("전체", 100000, 0, 100000)])

    def test_leap_day_and_invalid_month(self):
        self.add("2028-02-29", 1000, "식비")
        self.assertEqual(budget.budget_table(self.store, self.cfg, "2028-02")[-1][2], 1000)
        with self.assertRaises(ValueError):
            budget.budget_table(self.store, self.cfg, "2026-13")

    def test_does_not_change_data_configuration_or_return_cached_rows(self):
        self.add("2026-11-01", 1000, "식비")
        before, cfg = copy.deepcopy(self.store.data), copy.deepcopy(self.cfg)
        rows = budget.budget_table(self.store, self.cfg, "2026-11")
        rows.clear()
        self.assertEqual(self.store.data, before)
        self.assertEqual(self.cfg, cfg)
        self.assertEqual(len(budget.budget_table(self.store, self.cfg, "2026-11")), 2)

    def test_cli_passes_numeric_columns_and_separate_total_to_shared_formatter(self):
        self.add("2026-11-01", 1000, "식비")
        self.store.save()
        self.cfg["data"] = self.store.path
        config_path = self.path("config.json")
        with open(config_path, "w", encoding="utf-8") as stream:
            json.dump(self.cfg, stream)
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        lines = []
        with patch.object(textfmt, "table", return_value="공통 표 출력") as formatter:
            code = cli.main(["--config", config_path, "budget", "table", "--month", "2026-11"],
                            out=lines.append)
        self.assertEqual(code, 0)
        formatter.assert_called_once_with(["분류", "예산", "실제", "차이"],
            [("식비", 50000, 1000, 49000)], total=("전체", 100000, 1000, 99000), numeric={1, 2, 3})
        self.assertEqual(lines, ["공통 표 출력", "전체 예산은 월 전체 예산 설정 기준입니다."])
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)
