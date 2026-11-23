"""기능 5 기본 필수: 월 예산, 초과·잔액, 회비 입금, 통장 잔고."""
import copy
import datetime as dt
from unittest.mock import patch

from helpers import NAMES, StoreCase
from moim.features import budget

KIM, LEE, PARK = NAMES


class BudgetBasicTest(StoreCase):
    def expense(self, day, amount, deleted=False):
        self.store.data["expenses"].append({
            "id": len(self.store.data["expenses"]) + 1, "date": day,
            "amount": amount, "deleted": deleted,
        })

    def test_month_boundaries_and_deleted_expenses(self):
        for day, amount, deleted in [
            ("2026-10-31", 900, False), ("2026-11-01", 30000, False),
            ("2026-11-30", 70000, False), ("2026-12-01", 800, False),
            ("2026-11-15", 500, True),
        ]:
            self.expense(day, amount, deleted)
        self.assertEqual(budget.month_status(self.store, self.cfg, "2026-11"),
                         {"budget": 100000, "spent": 100000,
                          "remaining": 0, "over": False})
        self.expense("2026-11-30", 1)
        status = budget.month_status(self.store, self.cfg, (2026, 11))
        self.assertEqual((status["remaining"], status["over"]), (-1, True))

    def test_today_cutoff_before_inside_and_after_month(self):
        self.expense("2026-11-01", 100)
        self.expense("2026-11-15", 200)
        self.expense("2026-11-30", 400)
        for today, expected in [("2026-10-31", 0), ("2026-11-15", 300),
                                (dt.date(2026, 12, 1), 700)]:
            with self.subTest(today=today):
                self.assertEqual(budget.month_status(
                    self.store, self.cfg, "2026-11", today)["spent"], expected)

    def test_leap_day_and_zero_budget(self):
        self.cfg["budget"]["monthly"] = 0
        self.expense("2028-02-29", 1)
        self.assertEqual(budget.month_status(self.store, self.cfg, "2028-02")["spent"], 1)
        self.assertTrue(budget.month_status(self.store, self.cfg, "2028-02")["over"])

    def test_invalid_month_budget_and_today(self):
        for month in ["2026-13", "0000-01", (2026, "11"), None]:
            with self.subTest(month=month), self.assertRaises(ValueError):
                budget.month_status(self.store, self.cfg, month)
        with self.assertRaises(ValueError):
            budget.month_status(self.store, {}, "2026-11")
        self.cfg["budget"]["monthly"] = -1
        with self.assertRaises(ValueError):
            budget.month_status(self.store, self.cfg, "2026-11")
        self.cfg["budget"]["monthly"] = 100
        with self.assertRaises(ValueError):
            budget.month_status(self.store, self.cfg, "2026-11", "2026-02-29")

    def test_payment_format_rounding_and_no_automatic_save(self):
        with patch.object(self.store, "save") as save:
            payment = budget.record_payment(self.store, dt.date(2026, 11, 2),
                                            LEE, "1,234.5원", "11월 회비")
            save.assert_not_called()
        self.assertEqual(payment, {"date": "2026-11-02", "member": LEE,
                                  "amount": 1235, "memo": "11월 회비", "source": "manual"})
        self.assertEqual(self.store.data["payments"], [payment])
        self.store.save()
        self.store.load()
        self.assertEqual(self.store.data["payments"], [payment])

    def test_invalid_payment_leaves_store_unchanged(self):
        before = copy.deepcopy(self.store.data)
        for day, member, amount in [("2026-02-29", KIM, 1),
                                    ("2026-11-02", "없는사람", 1)]:
            with self.subTest(day=day, member=member), self.assertRaises(ValueError):
                budget.record_payment(self.store, day, member, amount)
        for amount in [0, -1, "0.4", True, "abc", "NaN", "Infinity"]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                budget.record_payment(self.store, "2026-11-02", KIM, amount)
        self.assertEqual(self.store.data, before)

    def test_null_payments_treated_as_empty(self):
        self.store.data["payments"] = None
        self.assertEqual(budget.treasury_balance(self.store), 0)
        self.assertIsNone(self.store.data["payments"])
        payment = budget.record_payment(self.store, "2026-11-02", KIM, 1)
        self.assertEqual(self.store.data["payments"], [payment])

    def test_broken_payments_container_is_rejected(self):
        for payments in [{}, "broken", 0]:
            self.store.data["payments"] = payments
            with self.subTest(payments=payments):
                with self.assertRaises(ValueError):
                    budget.treasury_balance(self.store)
                with self.assertRaises(ValueError):
                    budget.record_payment(self.store, "2026-11-02", KIM, 1)
                self.assertEqual(self.store.data["payments"], payments)

    def test_balance_cutoff_deleted_expenses_and_negative_balance(self):
        budget.record_payment(self.store, "2026-11-01", KIM, 10000)
        budget.record_payment(self.store, "2026-11-30", LEE, 20000)
        self.expense("2026-11-01", 4000)
        self.expense("2026-11-30", 7000)
        self.expense("2026-11-15", 50000, deleted=True)
        self.assertEqual(budget.treasury_balance(self.store, "2026-11-01"), 6000)
        self.assertEqual(budget.treasury_balance(self.store, "2026-11-30"), 19000)
        self.assertEqual(budget.treasury_balance(self.store), 19000)
        self.expense("2026-12-01", 20000)
        self.assertEqual(budget.treasury_balance(self.store), -1000)
        with self.assertRaises(ValueError):
            budget.treasury_balance(self.store, "2026-13-01")

    def test_read_only_queries_do_not_change_data_or_config(self):
        before, cfg = copy.deepcopy(self.store.data), copy.deepcopy(self.cfg)
        budget.month_status(self.store, self.cfg, "2026-11")
        budget.treasury_balance(self.store)
        self.assertEqual(self.store.data, before)
        self.assertEqual(self.cfg, cfg)
