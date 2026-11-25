import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from moim.common.store import Store


class _SteppingDateTime(datetime):
    _current = datetime(2026, 11, 23, 12, 0, 0)
    _step = timedelta(microseconds=500)

    @classmethod
    def configure(cls, start: datetime, step: timedelta = timedelta(microseconds=500)):
        cls._current = start
        cls._step = step

    @classmethod
    def now(cls, tz=None):
        val = cls._current
        cls._current = cls._current + cls._step
        if tz is not None:
            return val.replace(tzinfo=tz)
        return val


class TestStoreBackupAndRecovery(unittest.TestCase):
    def test_keep_validation_in_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            for invalid in (-1, True, False, "10", 2.5):
                with self.subTest(keep=invalid):
                    with self.assertRaises(ValueError):
                        Store(data_path, keep=invalid)

    def test_backups_returns_empty_when_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path)
            self.assertEqual(store.backups(), [])

    def test_first_save_creates_no_backup_and_twelve_saves_keep_ten(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            _SteppingDateTime.configure(datetime(2026, 11, 23, 12, 0, 0), timedelta(microseconds=500))
            store = Store(data_path, keep=10)

            with patch("moim.common.store.datetime", _SteppingDateTime):
                # 1번째 저장: 직전 파일이 없으므로 백업 0개
                store.data["next_id"] = 1
                store.save()
                self.assertEqual(store.backups(), [])

                # 이후 12번 추가 저장(총 13번 저장): 직전 12개 중 최근 10개만 유지
                for step in range(2, 14):
                    store.data["next_id"] = step
                    store.data["expenses"] = [
                        {
                            "id": step,
                            "date": "2026-11-23",
                            "payer": "민기슬",
                            "amount": step * 1000,
                            "members": ["민기슬"],
                        }
                    ]
                    store.save()

            backups = store.backups()
            self.assertEqual(len(backups), 10)
            self.assertEqual(backups, sorted(backups))

            with open(backups[0], encoding="utf-8") as f:
                oldest_kept = json.load(f)
            with open(backups[-1], encoding="utf-8") as f:
                latest_kept = json.load(f)

            self.assertEqual(oldest_kept["next_id"], 3)
            self.assertEqual(latest_kept["next_id"], 12)

    def test_backups_ignores_non_matching_filenames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            backup_dir = os.path.join(tmpdir, "backup")
            os.makedirs(backup_dir, exist_ok=True)

            valid_name = "data-20261123-120000-000001.json"
            valid_path = os.path.join(backup_dir, valid_name)
            with open(valid_path, "w", encoding="utf-8") as f:
                json.dump({"members": [], "expenses": []}, f)

            for ignored_name in (
                "data-old.json",
                "data-20261123-120000.json",
                "data-20261123-120000-000001.json.bak",
                "other.json",
            ):
                with open(os.path.join(backup_dir, ignored_name), "w", encoding="utf-8") as f:
                    f.write("{}")

            store = Store(data_path, backup_dir=backup_dir)
            self.assertEqual(store.backups(), [valid_path])

    def test_save_keep_zero_removes_existing_backups_without_creating_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            _SteppingDateTime.configure(datetime(2026, 11, 23, 12, 0, 0), timedelta(seconds=1))
            store = Store(data_path, keep=2)

            with patch("moim.common.store.datetime", _SteppingDateTime):
                store.data["next_id"] = 1
                store.save()
                store.data["next_id"] = 2
                store.save()
                self.assertEqual(len(store.backups()), 1)

                store.keep = 0
                store.data["next_id"] = 3
                store.save()
                self.assertEqual(store.backups(), [])

    def test_save_failure_preserves_original_file_and_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            _SteppingDateTime.configure(datetime(2026, 11, 23, 12, 0, 0), timedelta(seconds=1))
            store = Store(data_path)

            with patch("moim.common.store.datetime", _SteppingDateTime):
                store.data["next_id"] = 1
                store.save()
                store.data["next_id"] = 7
                store.save()

            backups_before = store.backups()
            self.assertEqual(len(backups_before), 1)

            store.data["next_id"] = 99
            store.data["expenses"] = [{"bad": {1, 2, 3}}]
            with self.assertRaises(TypeError):
                store.save()

            self.assertEqual(store.backups(), backups_before)
            reloaded = Store(data_path).load()
            self.assertEqual(reloaded.data["next_id"], 7)

            leftover_tmp = [name for name in os.listdir(tmpdir) if name.startswith(".tmp-")]
            self.assertEqual(leftover_tmp, [])

    def test_recover_moves_broken_file_and_restores_latest_valid_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            _SteppingDateTime.configure(datetime(2026, 11, 23, 12, 0, 0), timedelta(seconds=1))
            store = Store(data_path)

            with patch("moim.common.store.datetime", _SteppingDateTime):
                store.data["next_id"] = 10
                store.save()
                store.data["next_id"] = 20
                store.save()
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

    def test_recover_skips_invalid_shape_and_corrupted_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            _SteppingDateTime.configure(datetime(2026, 11, 23, 12, 0, 0), timedelta(seconds=1))
            store = Store(data_path)

            with patch("moim.common.store.datetime", _SteppingDateTime):
                for next_id in (10, 20, 30, 40):
                    store.data["next_id"] = next_id
                    store.save()

            backups = store.backups()
            self.assertEqual(len(backups), 3)
            valid_oldest_backup = backups[0]
            invalid_shape_backup = backups[1]
            corrupted_latest_backup = backups[2]

            with open(invalid_shape_backup, "w", encoding="utf-8") as f:
                json.dump({"members": "not-a-list", "expenses": []}, f)

            with open(corrupted_latest_backup, "w", encoding="utf-8") as f:
                f.write("not-json")

            with open(data_path, "w", encoding="utf-8") as f:
                f.write("{broken")

            target = Store(data_path).recover()
            self.assertEqual(target.recovered_from, valid_oldest_backup)
            self.assertEqual(target.data["next_id"], 10)

    def test_recover_broken_file_name_collision_appends_suffix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            fixed_time = datetime(2026, 11, 23, 12, 30, 45)
            _SteppingDateTime.configure(fixed_time, timedelta(seconds=1))
            store = Store(data_path)

            with patch("moim.common.store.datetime", _SteppingDateTime):
                store.data["next_id"] = 5
                store.save()
                store.data["next_id"] = 6
                store.save()

            existing_broken = f"{data_path}.broken-20261123-123045"
            with open(existing_broken, "w", encoding="utf-8") as f:
                f.write("old-broken")

            with open(data_path, "w", encoding="utf-8") as f:
                f.write("{broken")

            _SteppingDateTime.configure(fixed_time, timedelta(0))
            with patch("moim.common.store.datetime", _SteppingDateTime):
                Store(data_path).recover()

            self.assertTrue(os.path.exists(existing_broken))
            self.assertTrue(os.path.exists(f"{existing_broken}-1"))

    def test_recover_raises_when_no_valid_backup_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            with open(data_path, "w", encoding="utf-8") as f:
                f.write("{broken")

            store = Store(data_path)
            with self.assertRaises(ValueError):
                store.recover()
            self.assertTrue(os.path.exists(data_path))


if __name__ == "__main__":
    unittest.main()
