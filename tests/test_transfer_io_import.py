import json
import unittest
from helpers import NAMES, StoreCase
from moim import cli
from moim.features import transfer_io

KIM, LEE, PARK = NAMES


class TestTransferIoImport(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": KIM, "joined": "2026-01-01"},
            {"name": LEE, "joined": "2026-01-01"},
            {"name": PARK, "joined": "2026-01-01"},
        ]

    def test_import_csv_cp949_mapping_duplicates_and_errors(self):
        self.store.data["expenses"] = [
            {
                "id": 1,
                "date": "2026-11-01",
                "payer": KIM,
                "amount": 10000,
                "category": "식비",
                "members": list(NAMES),
                "memo": "기존 지출",
            }
        ]
        self.store.data["next_id"] = 2
        self.store.data["locks"] = {"2026-10": "2026-10-31"}

        csv_path = self.path("import_cp949.csv")
        csv_lines = (
            "지출일,결제자,금액,분류,참여자,비율,메모",
            f'2026-11-05,{LEE},24000,교통,"{KIM},{LEE}","{KIM}:2,{LEE}:1",택시',
            f"2026-11-01,{KIM},10000,식비,,,장부 중복",
            f"2026-11-05,{LEE},24000,교통,,,파일 중복",
            "2026-11-06,없는사람,5000,식비,,,미등록 회원 오류",
            f"2026-10-15,{KIM},8000,식비,,,확정 기간 오류",
            f"2026-11-07,{PARK},15000,,,,기본 참여자",
        )
        with open(csv_path, "w", encoding="cp949", newline="") as f:
            f.write("\n".join(csv_lines) + "\n")

        mapping = {
            "지출일": "date",
            "결제자": "payer",
            "금액": "amount",
            "분류": "category",
            "참여자": "members",
            "비율": "weights",
            "메모": "memo",
        }
        res = transfer_io.import_csv(self.store, csv_path, mapping=mapping)
        self.assertEqual(res["encoding"], "cp949")
        self.assertEqual(res["added"], list((2, 3)))
        self.assertEqual(res["duplicates"], list((3, 4)))
        self.assertEqual(len(res["errors"]), 2)
        first_err, second_err = res["errors"]
        first_err_line, _ = first_err
        second_err_line, _ = second_err
        self.assertEqual((first_err_line, second_err_line), (5, 6))
        self.assertEqual(len(self.store.data["expenses"]), 3)

    def test_import_csv_preview_does_not_mutate_store(self):
        csv_path = self.path("preview.csv")
        csv_lines = (
            "date,payer,amount,memo",
            f"2026-11-10,{KIM},12000,점심",
            f"2026-11-11,{LEE},9000,커피",
            "2026-11-12,없는사람,5000,오류행",
        )
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("\n".join(csv_lines) + "\n")

        res = transfer_io.import_csv(self.store, csv_path, preview=True)
        self.assertEqual(res["added"], list((2, 3)))
        self.assertEqual(len(res["errors"]), 1)
        self.assertEqual(self.store.data["expenses"], list())

    def test_cli_import_csv_preview_and_apply(self):
        self.store.save()
        cfg_path = self.path("config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path}, f)

        csv_path = self.path("cli_import.csv")
        csv_lines = (
            "날짜,사람,돈",
            f"2026-11-12,{KIM},18000",
        )
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(csv_lines) + "\n")

        out_lines = []
        code = cli.main(
            [
                "--config",
                cfg_path,
                "io",
                "import-csv",
                csv_path,
                "--map",
                "날짜=date,사람=payer,돈=amount",
                "--preview",
            ],
            out=out_lines.append,
        )
        self.assertEqual(code, 0)
        (preview_msg,) = out_lines
        self.assertIn("(미리 보기)", preview_msg)
        self.assertEqual(self.store.load().data["expenses"], list())

        out_lines.clear()
        code = cli.main(
            [
                "--config",
                cfg_path,
                "io",
                "import-csv",
                csv_path,
                "--map",
                "날짜=date,사람=payer,돈=amount",
            ],
            out=out_lines.append,
        )
        self.assertEqual(code, 0)
        (apply_msg,) = out_lines
        self.assertIn("추가 1건", apply_msg)
        self.assertEqual(len(self.store.load().data["expenses"]), 1)


if __name__ == "__main__":
    unittest.main()
