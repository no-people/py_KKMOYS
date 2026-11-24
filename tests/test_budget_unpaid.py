"""교수님 기준: 월 1일 또는 말일에 회원인 사람, 월 입금 합계와 명부 순서."""
import copy
import json

from helpers import NAMES, StoreCase
from moim import cli
from moim.features import budget

KIM, LEE, PARK = NAMES


class UnpaidDuesTest(StoreCase):
    def payment(self, name, amount, day="2026-11-02", source="manual"):
        self.store.data.setdefault("payments", []).append({
            "member": name, "amount": amount, "date": day, "memo": "", "source": source})

    def test_endpoint_membership_and_roster_order(self):
        self.store.data["members"] = [
            {"name": "말일가입", "joined": "2026-11-30", "left": None},
            {"name": "초일탈퇴", "joined": "2026-09-01", "left": "2026-11-01"},
            {"name": "중간만회원", "joined": "2026-11-02", "left": "2026-11-29"},
            {"name": "이전탈퇴", "joined": "2026-09-01", "left": "2026-10-31"},
            {"name": "다음달가입", "joined": "2026-12-01", "left": None},
        ]
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2026-11"),
                         [("말일가입", 0, 20000), ("초일탈퇴", 0, 20000)])

    def test_partial_payments_both_sources_and_month_boundaries(self):
        self.payment(KIM, 7000, "2026-11-01")
        self.payment(KIM, 5000, "2026-11-30", "bank")
        self.payment(KIM, 20000, "2026-10-31")
        self.payment(KIM, 20000, "2026-12-01")
        self.payment(LEE, 20000)
        self.payment(PARK, 25000)
        self.assertEqual(budget.unpaid(self.store, self.cfg, (2026, 11)), [(KIM, 12000, 8000)])

    def test_leap_month_last_day_is_eligible(self):
        self.store.data["members"] = [{"name": KIM, "joined": "2028-02-29", "left": None}]
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2028-02"), [(KIM, 0, 20000)])

    def test_missing_null_payments_empty_roster_and_zero_dues(self):
        self.store.data.pop("payments", None)
        self.assertEqual(len(budget.unpaid(self.store, self.cfg, "2026-11")), 3)
        self.store.data["payments"] = None
        self.assertEqual(len(budget.unpaid(self.store, self.cfg, "2026-11")), 3)
        self.assertIsNone(self.store.data["payments"])
        self.cfg["dues"]["monthly"] = 0
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2026-11"), [])
        self.store.data["members"] = []
        self.assertEqual(budget.unpaid(self.store, self.cfg, "2026-11"), [])

    def test_bad_month_dues_or_payment_container_is_rejected(self):
        with self.assertRaises(ValueError):
            budget.unpaid(self.store, self.cfg, "2026-13")
        with self.assertRaises(ValueError):
            budget.unpaid(self.store, {}, "2026-11")
        self.cfg["dues"]["monthly"] = -1
        with self.assertRaises(ValueError):
            budget.unpaid(self.store, self.cfg, "2026-11")
        self.cfg["dues"]["monthly"] = 20000
        self.store.data["payments"] = {}
        with self.assertRaises(ValueError):
            budget.unpaid(self.store, self.cfg, "2026-11")

    def test_query_leaves_original_store_and_configuration_unchanged(self):
        self.payment(KIM, 5000)
        before, cfg = copy.deepcopy(self.store.data), copy.deepcopy(self.cfg)
        budget.unpaid(self.store, self.cfg, "2026-11")
        self.assertEqual(self.store.data, before)
        self.assertEqual(self.cfg, cfg)

    def test_cli_unpaid_and_no_save(self):
        self.payment(KIM, 19000)
        self.payment(LEE, 20000)
        self.payment(PARK, 20000)
        self.store.save()
        self.cfg["data"] = self.store.path
        config_path = self.path("config.json")
        with open(config_path, "w", encoding="utf-8") as stream:
            json.dump(self.cfg, stream)
        with open(self.store.path, "rb") as stream:
            before = stream.read()
        lines = []
        self.assertEqual(cli.main(["--config", config_path, "budget", "unpaid",
                                   "--month", "2026-11"], out=lines.append), 0)
        self.assertEqual(lines, [f"{KIM}: 납부 19,000원, 미납 1,000원"])
        with open(self.store.path, "rb") as stream:
            self.assertEqual(stream.read(), before)
