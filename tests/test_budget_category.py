"""확장 필수: 분류 예산, 80% 초과(같으면 경보 없음), 합계 보존."""
import copy
import json

from helpers import StoreCase
from moim import cli
from moim.common.rules import UNCATEGORIZED
from moim.features import budget


class CategoryBudgetTest(StoreCase):
    def add(self, amount, category="식비", day="2026-11-30", deleted=False):
        self.store.data["expenses"].append({"id": len(self.store.data["expenses"]) + 1,
            "date": day, "amount": amount, "category": category, "deleted": deleted})

    def test_exact_threshold_one_won_over_and_budget_over(self):
        self.cfg["budget"] = {"monthly": 100, "by_category": {"식비": 100}}
        for amount, warn, over in [(80, False, False), (81, True, False),
                                   (100, True, False), (101, True, True)]:
            with self.subTest(amount=amount):
                self.store.data["expenses"] = []
                self.add(amount)
                item = budget.category_status(self.store, self.cfg, "2026-11")["식비"]
                self.assertEqual((item["remaining"], item["warn"], item["over"]),
                                 (100 - amount, warn, over))
                monthly = budget.month_status(self.store, self.cfg, "2026-11")
                self.assertEqual((monthly["warn"], monthly["over"]), (warn, over))

    def test_decimal_threshold_has_no_float_rounding(self):
        self.cfg["budget"]["by_category"] = {"식비": 110}
        self.cfg["warn_ratio"] = "0.1"
        self.add(11)
        self.assertFalse(budget.category_status(self.store, self.cfg, "2026-11")["식비"]["warn"])
        self.add(1)
        self.assertTrue(budget.category_status(self.store, self.cfg, "2026-11")["식비"]["warn"])

    def test_whitespace_uncategorized_unbudgeted_and_deleted(self):
        self.add(100, " 식비 ", "2026-11-01")
        self.add(200, "식비")
        self.add(300, "   ")
        self.add(500, "교통")
        self.add(9000, "식비", deleted=True)
        self.add(8000, "식비", "2026-12-01")
        result = budget.category_status(self.store, self.cfg, "2026-11")
        self.assertEqual(result["식비"]["spent"], 300)
        self.assertEqual(result[UNCATEGORIZED], {"budget": 0, "spent": 300,
                         "remaining": -300, "over": True, "warn": True})
        self.assertEqual(result["교통"]["budget"], 0)
        self.assertEqual(sum(item["spent"] for item in result.values()), 1100)
        self.assertEqual(budget.month_status(self.store, self.cfg, "2026-11")["spent"], 1100)

    def test_budget_without_expenses_and_zero_budget(self):
        self.cfg["budget"]["by_category"] = {"식비": 0, "교통": 1000}
        result = budget.category_status(self.store, self.cfg, (2026, 11))
        self.assertEqual(list(result), ["식비", "교통"])
        self.assertEqual(result["교통"]["remaining"], 1000)
        self.assertFalse(result["식비"]["warn"])
        self.assertFalse(result["식비"]["over"])

    def test_invalid_configuration_is_rejected(self):
        for value in [None, [], "invalid"]:
            self.cfg["budget"]["by_category"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.category_status(self.store, self.cfg, "2026-11")
        for limits in [{"식비": -1}, {"": 100}, {" 식비 ": 100}, {3: 100},
                       {"식비": "Infinity"}]:
            self.cfg["budget"]["by_category"] = limits
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                budget.category_status(self.store, self.cfg, "2026-11")
        self.cfg["budget"]["by_category"] = {}
        for ratio in [-0.1, 1.1, "NaN", "Infinity", True]:
            self.cfg["warn_ratio"] = ratio
            with self.subTest(ratio=ratio), self.assertRaises(ValueError):
                budget.category_status(self.store, self.cfg, "2026-11")

    def test_queries_leave_store_and_configuration_unchanged(self):
        self.add(100)
        before, cfg = copy.deepcopy(self.store.data), copy.deepcopy(self.cfg)
        budget.category_status(self.store, self.cfg, "2026-11")
        budget.month_status(self.store, self.cfg, "2026-11")
        self.assertEqual(self.store.data, before)
        self.assertEqual(self.cfg, cfg)

    def test_categories_command_and_monthly_warning(self):
        self.cfg["budget"] = {"monthly": 100, "by_category": {"식비": 100}}
        self.cfg["data"] = self.store.path
        self.add(81)
        self.store.save()
        config_path = self.path("config.json")
        with open(config_path, "w", encoding="utf-8") as stream:
            json.dump(self.cfg, stream)
        lines = []
        self.assertEqual(cli.main(["--config", config_path, "budget", "categories",
                                   "--month", "2026-11"], out=lines.append), 0)
        self.assertEqual(lines, ["식비: 예산 100원, 사용 81원, 잔액 19원 (주의)"])
        lines.clear()
        cli.main(["--config", config_path, "budget", "status", "--month", "2026-11"],
                 out=lines.append)
        self.assertEqual(lines[-1], "예산 주의: 경보 기준 초과")
