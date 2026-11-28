import json
import os
import unittest
from helpers import NAMES, StoreCase
from moim import cli
from moim.features import transfer_io

KIM, LEE, PARK = NAMES


class TestTransferIoBackupRestore(StoreCase):
    def test_backup_all_and_restore_all_roundtrip(self):
        self.store.data["expenses"] = [
            {
                "id": 1,
                "date": "2026-11-01",
                "payer": KIM,
                "amount": 15000,
                "category": "식비",
                "members": list(NAMES),
                "memo": "점심",
            },
            {
                "id": 2,
                "date": "2026-11-02",
                "payer": LEE,
                "amount": 5000,
                "category": "교통",
                "members": list(NAMES),
                "deleted": True,
                "memo": "삭제된 항목",
            },
        ]
        self.store.data["payments"] = list(({"id": 1, "member": KIM, "amount": 20000, "date": "2026-11-01"},))
        self.store.data["next_id"] = 3
        self.store.save()

        bak_path = os.path.join(self.path("sub"), "full_backup.json")
        m_cnt, e_cnt = transfer_io.backup_all(self.store, bak_path)
        self.assertEqual((m_cnt, e_cnt), (3, 1))
        self.assertTrue(os.path.exists(bak_path))

        # 현재 자료를 변형한 뒤 백업에서 복원
        self.store.data["members"] = list()
        self.store.data["expenses"] = list()
        self.store.data["payments"] = list()

        rm_cnt, re_cnt = transfer_io.restore_all(self.store, bak_path)
        self.assertEqual((rm_cnt, re_cnt), (3, 1))
        self.assertEqual(len(self.store.data["members"]), 3)
        self.assertEqual(len(self.store.data["expenses"]), 2)
        self.assertEqual(len(self.store.data["payments"]), 1)
        self.assertEqual(self.store.data["next_id"], 3)

    def test_restore_all_rejects_broken_or_missing_without_mutating(self):
        self.store.data["expenses"] = [
            {"id": 1, "date": "2026-11-01", "payer": KIM, "amount": 10000, "category": "식비", "members": list(NAMES)}
        ]
        with self.assertRaises(FileNotFoundError):
            transfer_io.restore_all(self.store, self.path("no_such_backup.json"))

        bad_json = self.path("broken.json")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("{invalid")
        with self.assertRaises(ValueError):
            transfer_io.restore_all(self.store, bad_json)

        bad_shape = self.path("bad_shape.json")
        with open(bad_shape, "w", encoding="utf-8") as f:
            json.dump({"only": "wrong"}, f)
        with self.assertRaises(ValueError):
            transfer_io.restore_all(self.store, bad_shape)

        self.assertEqual(len(self.store.data["expenses"]), 1)

    def test_cli_backup_default_dir_and_restore(self):
        self.store.data["expenses"] = [
            {"id": 1, "date": "2026-11-05", "payer": PARK, "amount": 25000, "category": "식비", "members": list(NAMES)}
        ]
        self.store.save()

        bak_dir = self.path("my_backups")
        cfg_path = self.path("config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path, "backup_dir": bak_dir}, f)

        lines = []
        code = cli.main(["--config", cfg_path, "io", "backup"], out=lines.append)
        self.assertEqual(code, 0)
        (bak_line,) = lines
        self.assertIn("전체 백업 완료", bak_line)
        created = [os.path.join(bak_dir, name) for name in os.listdir(bak_dir) if name.startswith("full-backup-")]
        self.assertEqual(len(created), 1)
        (bak_file,) = created

        # 원본 비운 뒤 CLI restore 실행
        self.store.data["expenses"] = list()
        self.store.save()

        lines.clear()
        code = cli.main(["--config", cfg_path, "io", "restore", bak_file], out=lines.append)
        self.assertEqual(code, 0)
        (res_line,) = lines
        self.assertIn("전체 복원 완료", res_line)
        self.assertEqual(len(self.store.load().data["expenses"]), 1)


if __name__ == "__main__":
    unittest.main()
