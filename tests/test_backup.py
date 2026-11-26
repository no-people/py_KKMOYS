import json
import os
import tempfile
import time
import unittest
from unittest import mock

from moim.common.store import Store


class TestStoreBackupCleanup(unittest.TestCase):
    def test_save_keeps_latest_backups_after_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path, keep=2)

            for idx in range(1, 5):
                store.data["next_id"] = idx
                store.save()
                time.sleep(0.002)

            backups = store.backups()
            self.assertEqual(len(backups), 2)
            with open(backups[-1], encoding="utf-8") as f:
                self.assertEqual(json.load(f)["next_id"], 3)

    def test_replace_failure_preserves_original_and_existing_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            store = Store(data_path, keep=1)

            store.data["next_id"] = 1
            store.save()
            time.sleep(0.002)

            store.data["next_id"] = 2
            store.save()
            existing_backups = store.backups()
            self.assertEqual(len(existing_backups), 1)

            store.data["next_id"] = 3
            with mock.patch("moim.common.store.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    store.save()

            reloaded = Store(data_path).load()
            self.assertEqual(reloaded.data["next_id"], 2)
            self.assertEqual(store.backups(), existing_backups)


if __name__ == "__main__":
    unittest.main()
