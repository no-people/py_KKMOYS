"""선택 기능: 당일 포함한 월말 예측, 사사오입, 윤년과 월 경계."""
import copy
import datetime as dt
import json

from helpers import StoreCase
from moim import cli
from moim.features import budget


class ForecastTest(StoreCase):
    def add(self, day, amount, deleted=False):
        self.store.data["expenses"].append({"id": len(self.store.data["expenses"]) + 1,
            "date": day, "amount": amount, "deleted": deleted})

    def test_period_includes_first_and_today_but_not_future_or_deleted(self):
        for day, amount, deleted in [
            ("2026-10-31", 999, False), ("2026-11-01", 3000, False),
            ("2026-11-15", 6000, False), ("2026-11-16", 8888, False),
            ("2026-11-12", 7777, True), ("2026-12-01", 999, False),
        ]:
            self.add(day, amount, deleted)
        self.assertEqual(budget.forecast(self.store, "2026-11", "2026-11-15"), 18000)

    def test_round_half_up_and_below_half(self):
        self.add("2026-11-01", 1)
        self.assertEqual(budget.forecast(self.store, "2026-11", "2026-11-12"), 3)
        self.store.data["expenses"][0]["amount"] = 2
        self.assertEqual(budget.forecast(self.store, "2026-11", "2026-11-25"), 2)

    def test_first_and_last_day(self):
        self.add("2026-12-01", 10)
        self.add("2026-12-31", 100)
        self.assertEqual(budget.forecast(self.store, (2026, 12), dt.date(2026, 12, 1)), 310)
        self.assertEqual(budget.forecast(self.store, "2026-12", "2026-12-31"), 110)

    def test_february_uses_actual_days_including_leap_year(self):
        self.add("2028-02-01", 10)
        self.add("2026-02-01", 10)
        self.assertEqual(budget.forecast(self.store, "2028-02", "2028-02-02"), 145)
        self.assertEqual(budget.forecast(self.store, "2026-02", "2026-02-02"), 140)

    def test_empty_month_and_datetime_input(self):
        self.assertEqual(budget.forecast(self.store, "2026-11",
                                        dt.datetime(2026, 11, 12, 23, 59)), 0)

    def test_invalid_month_date_and_date_outside_month(self):
        for month, day in [("2026-13", "2026-11-01"), ("2026-11", "2026-11-31"),
                            ("2026-11", "2026-10-31"), ("2026-11", "2026-12-01"),
                            ("2026-02", "2026-02-29")]:
            with self.subTest(month=month, day=day), self.assertRaises(ValueError):
                budget.forecast(self.store, month, day)

    def test_query_does_not_change_data(self):
        self.add("2026-11-01", 1)
        before = copy.deepcopy(self.store.data)
        budget.forecast(self.store, "2026-11", "2026-11-12")
        self.assertEqual(self.store.data, before)

    def test_cli_output_and_no_file_changes(self):
        self.add("2026-11-01", 1)
        self.store.save()
        config_path = self.path("config.json")
        with open(config_path, "w", encoding="utf-8") as stream:
            json.dump({"data": self.store.path}, stream)
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        lines = []
        self.assertEqual(cli.main(["--config", config_path, "budget", "forecast",
                                   "--month", "2026-11", "--today", "2026-11-12"],
                                  out=lines.append), 0)
        self.assertEqual(lines, ["2026-11 월말 예상 지출: 3원 (기준일: 2026-11-12)"])
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)
