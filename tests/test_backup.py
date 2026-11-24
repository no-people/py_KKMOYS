import json
import os
import tempfile
import time
import unittest

from moim.common.store import Store


class TestStoreBackupAndRecovery(unittest.TestCase):
    def test_backups_returns_empty_when_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path)
            self.assertEqual(store.backups(), [])

    def test_save_creates_backups_and_keeps_latest_10(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path, keep=10)

            for i in range(13):
                store.data["next_id"] = i + 1
                store.data["expenses"] = [
                    {
                        "id": i + 1,
                        "date": "2026-11-23",
                        "payer": "민기슬",
                        "amount": (i + 1) * 1000,
                        "members": ["민기슬"],
                    }
                ]
                store.save()
                time.sleep(0.002)

            backups = store.backups()
            self.assertEqual(len(backups), 10)
            self.assertEqual(backups, sorted(backups))

            with open(backups[0], encoding="utf-8") as f:
                oldest_kept = json.load(f)
            with open(backups[-1], encoding="utf-8") as f:
                latest_kept = json.load(f)

            self.assertEqual(oldest_kept["next_id"], 3)
            self.assertEqual(latest_kept["next_id"], 12)

    def test_save_failure_preserves_original_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path)
            store.data["next_id"] = 7
            store.save()

            store.data["next_id"] = 99
            store.data["expenses"] = [{"bad": {1, 2, 3}}]
            with self.assertRaises(TypeError):
                store.save()

            reloaded = Store(data_path).load()
            self.assertEqual(reloaded.data["next_id"], 7)

    def test_recover_moves_broken_file_and_restores_latest_valid_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path)

            store.data["next_id"] = 10
            store.save()
            time.sleep(0.002)

            store.data["next_id"] = 20
            store.save()
            time.sleep(0.002)

            store.data["next_id"] = 30
            store.save()
            latest_backup = store.backups()[-1]

            with open(data_path, "w", encoding="utf-8") as f:
                f.write('{"members": [')

            broken_store = Store(data_path)
            with self.assertRaises(json.JSONDecodeError):
                broken_store.load()

            recovered = broken_store.recover()
            self.assertIs(recovered, broken_store)
            self.assertEqual(broken_store.recovered_from, latest_backup)
            self.assertEqual(broken_store.data["next_id"], 20)

            broken_files = [
                name for name in os.listdir(tmpdir)
                if name.startswith("data.json.broken-")
            ]
            self.assertEqual(len(broken_files), 1)

    def test_recover_skips_corrupted_latest_backup_and_uses_previous(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path)

            store.data["next_id"] = 10
            store.save()
            time.sleep(0.002)

            store.data["next_id"] = 20
            store.save()
            time.sleep(0.002)

            store.data["next_id"] = 30
            store.save()

            backups = store.backups()
            valid_prev_backup = backups[-2]
            corrupted_latest_backup = backups[-1]

            with open(corrupted_latest_backup, "w", encoding="utf-8") as f:
                f.write("not-json")

            with open(data_path, "w", encoding="utf-8") as f:
                f.write("{broken")

            target = Store(data_path).recover()
            self.assertEqual(target.recovered_from, valid_prev_backup)
            self.assertEqual(target.data["next_id"], 10)

    def test_recover_raises_when_no_valid_backup_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            with open(data_path, "w", encoding="utf-8") as f:
                f.write("{broken")

            store = Store(data_path)
            with self.assertRaises(ValueError):
                store.recover()


if __name__ == "__main__":
    unittest.main()
