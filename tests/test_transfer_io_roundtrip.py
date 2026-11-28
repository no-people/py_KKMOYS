import csv
import json
import unittest
from helpers import NAMES, StoreCase
from moim import cli
from moim.features import transfer_io

KIM, LEE, PARK = NAMES


class TestTransferIoRoundtrip(StoreCase):
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
                "date": "2026-12-02",
                "payer": PARK,
                "amount": 18000,
                "category": "식비",
                "members": list(NAMES),
                "memo": "12월 모임",
            },
        ]

    def test_roundtrip_check_csv_and_json_match_and_diff(self):
        csv_path = self.path("rt.csv")
        transfer_io.export_csv(self.store, csv_path)
        self.assertEqual(transfer_io.roundtrip_check(self.store, csv_path), list())

        json_path = self.path("rt.json")
        transfer_io.export_json(
            self.store, json_path, start="2026-11-01", end="2026-11-30", category="교통"
        )
        self.assertEqual(
            transfer_io.roundtrip_check(
                self.store, json_path, start="2026-11-01", end="2026-11-30", category="교통"
            ),
            list(),
        )

        # 2번 지출 금액이 원본에서 변경된 경우 2번만 불일치 목록에 반환
        self.store.data["expenses"] = [
            self.store.data["expenses"].pop(0),
            {
                "id": 2,
                "date": "2026-11-15",
                "payer": LEE,
                "amount": 35000,
                "category": "교통",
                "members": list((KIM, LEE)),
                "weights": {KIM: 2, LEE: 1},
                "memo": "택시",
            },
            {
                "id": 3,
                "date": "2026-12-02",
                "payer": PARK,
                "amount": 18000,
                "category": "식비",
                "members": list(NAMES),
                "memo": "12월 모임",
            },
        ]
        self.assertEqual(transfer_io.roundtrip_check(self.store, csv_path), list((2,)))

    def test_roundtrip_check_detects_tampered_csv_row(self):
        csv_path = self.path("tampered.csv")
        transfer_io.export_csv(self.store, csv_path)
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        first_row, second_row, third_row = rows
        third_row["memo"] = "수정된 메모"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=transfer_io.EXPORT_FIELDS)
            writer.writeheader()
            writer.writerows((first_row, second_row, third_row))

        self.assertEqual(transfer_io.roundtrip_check(self.store, csv_path), list((3,)))

    def test_cli_roundtrip_command(self):
        self.store.save()
        cfg_path = self.path("config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path}, f)

        csv_path = self.path("cli_rt.csv")
        transfer_io.export_csv(self.store, csv_path, start="2026-11-01", end="2026-11-30")

        lines = []
        code = cli.main(
            ["--config", cfg_path, "io", "roundtrip", csv_path, "--month", "2026-11"],
            out=lines.append,
        )
        self.assertEqual(code, 0)
        (msg,) = lines
        self.assertIn("왕복 검증 일치", msg)


if __name__ == "__main__":
    unittest.main()
