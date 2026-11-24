import csv
import json
import unittest
from helpers import NAMES, StoreCase
from moim import cli
from moim.features import transfer_io

KIM, LEE, PARK = NAMES


class TestTransferIoExport(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["expenses"] = [
            {
                "id": 1,
                "date": "2026-11-01",
                "payer": KIM,
                "amount": 12000,
                "category": "식비",
                "members": list(NAMES),
                "memo": "점심",
            },
            {
                "id": 2,
                "date": "2026-11-15",
                "payer": LEE,
                "amount": 30000,
                "category": "교통",
                "members": list((KIM, LEE)),
                "weights": {KIM: 2, LEE: 1},
                "memo": "택시",
            },
            {
                "id": 3,
                "date": "2026-11-20",
                "payer": PARK,
                "amount": 9000,
                "category": "식비",
                "members": list(NAMES),
                "deleted": True,
                "memo": "삭제된 항목",
            },
            {
                "id": 4,
                "date": "2026-12-05",
                "payer": KIM,
                "amount": 50000,
                "category": "식비",
                "members": list(NAMES),
                "memo": "12월 회식",
            },
        ]

    def test_export_csv_bom_and_totals(self):
        out_path = self.path("out.csv")
        count, total = transfer_io.export_csv(self.store, out_path)
        self.assertEqual((count, total), (3, 92000))
        with open(out_path, "rb") as raw:
            self.assertEqual(raw.read(3), b"\xef\xbb\xbf")
        with open(out_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 3)
        _, second_row, _ = rows
        self.assertEqual(second_row["weights"], f"{KIM}:2,{LEE}:1")
        self.assertEqual(transfer_io.file_total(out_path), (92000, 3))
        self.assertEqual(transfer_io.verify_export(self.store, out_path), (True, 92000, 92000))

    def test_export_json_and_filtered_selection(self):
        out_path = self.path("nov_food.json")
        count, total = transfer_io.export_json(
            self.store, out_path, start="2026-11-01", end="2026-11-30", category="식비"
        )
        self.assertEqual((count, total), (1, 12000))
        with open(out_path, encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(len(loaded), 1)
        (first_item,) = loaded
        self.assertEqual(first_item["id"], 1)
        self.assertEqual(
            transfer_io.verify_export(self.store, out_path, start="2026-11-01", end="2026-11-30", category="식비"),
            (True, 12000, 12000),
        )
        self.assertEqual(transfer_io.verify_export(self.store, out_path), (False, 12000, 92000))

    def test_category_of_normalization_and_invalid_type(self):
        self.store.data["expenses"] = [
            {"id": 1, "date": "2026-11-01", "payer": KIM, "amount": 1000, "category": " 식비 ", "members": list(NAMES)},
            {"id": 2, "date": "2026-11-02", "payer": LEE, "amount": 2000, "category": "   ", "members": list(NAMES)},
        ]
        food_csv = self.path("food.csv")
        self.assertEqual(transfer_io.export_csv(self.store, food_csv, category="식비"), (1, 1000))
        with open(food_csv, encoding="utf-8-sig", newline="") as f:
            (food_row,) = list(csv.DictReader(f))
        self.assertEqual(food_row["category"], "식비")

        uncat_csv = self.path("uncat.csv")
        self.assertEqual(transfer_io.export_csv(self.store, uncat_csv, category="미분류"), (1, 2000))
        with open(uncat_csv, encoding="utf-8-sig", newline="") as f:
            (uncat_row,) = list(csv.DictReader(f))
        self.assertEqual(uncat_row["category"], "미분류")

        self.store.data["expenses"].append(
            {"id": 3, "date": "2026-11-03", "payer": PARK, "amount": 3000, "category": 123, "members": list(NAMES)}
        )
        with self.assertRaises(ValueError):
            transfer_io.export_csv(self.store, self.path("bad.csv"))

    def test_cli_export_and_verify_commands(self):
        self.store.save()
        cfg_path = self.path("config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path}, f)

        csv_path = self.path("cli_export.csv")
        lines = []
        code = cli.main(
            ["--config", cfg_path, "io", "export-csv", csv_path, "--month", "2026-11"],
            out=lines.append,
        )
        self.assertEqual(code, 0)
        (output_line,) = lines
        self.assertIn("2건", output_line)
        self.assertIn("42,000원", output_line)

        lines.clear()
        code = cli.main(
            ["--config", cfg_path, "io", "verify", csv_path, "--month", "2026-11"],
            out=lines.append,
        )
        self.assertEqual(code, 0)
        (verify_line,) = lines
        self.assertIn("일치", verify_line)


if __name__ == "__main__":
    unittest.main()
