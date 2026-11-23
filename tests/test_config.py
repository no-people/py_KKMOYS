import json
import os
import tempfile
import unittest
from moim.common import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg_path = os.path.join(self.tmp.name, "config.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_missing_returns_defaults_with_resolved_paths(self):
        cfg = config.load(self.cfg_path)
        self.assertEqual(cfg["group"], "우리 모임")
        self.assertEqual(cfg["treasurer"], "")
        self.assertEqual(cfg["budget"], {"monthly": 0, "by_category": {}})
        self.assertEqual(cfg["dues"], {"monthly": 0})
        self.assertEqual(cfg["warn_ratio"], 0.8)
        for key, rel in (
            ("data", "data.json"),
            ("members_file", "members.csv"),
            ("rules", "rules.json"),
            ("backup_dir", "backups"),
            ("log_dir", "logs"),
        ):
            with self.subTest(key=key):
                self.assertEqual(cfg[key], os.path.join(self.tmp.name, rel))

    def test_load_partial_and_nested_override(self):
        custom = {
            "group": "파이썬 스터디",
            "treasurer": "김민수",
            "budget": {"monthly": 300000},
            "dues": {"monthly": 20000},
            "warn_ratio": 0.9,
        }
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(custom, f, ensure_ascii=False)

        cfg = config.load(self.cfg_path)
        self.assertEqual(cfg["group"], "파이썬 스터디")
        self.assertEqual(cfg["treasurer"], "김민수")
        self.assertEqual(cfg["budget"], {"monthly": 300000, "by_category": {}})
        self.assertEqual(cfg["dues"], {"monthly": 20000})
        self.assertEqual(cfg["warn_ratio"], 0.9)

    def test_load_invalid_json_raises_value_error(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("{broken json")
        with self.assertRaises(ValueError) as cm:
            config.load(self.cfg_path)
        self.assertIn("1번째 줄", str(cm.exception))

    def test_load_non_dict_or_null_path_raises_value_error(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(list((1, 2, 3)), f)
        with self.assertRaises(ValueError):
            config.load(self.cfg_path)

        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump({"data": None}, f)
        with self.assertRaises(ValueError):
            config.load(self.cfg_path)

    def test_save_default_and_duplicate_error(self):
        config.save_default(self.cfg_path)
        with open(self.cfg_path, encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved, config.DEFAULT)
        with self.assertRaises(FileExistsError):
            config.save_default(self.cfg_path)


if __name__ == "__main__":
    unittest.main()
