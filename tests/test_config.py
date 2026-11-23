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
        self.assertEqual(cfg["budget"], {"monthly": None, "by_category": {}})
        self.assertEqual(cfg["dues"], {"monthly": None})
        self.assertEqual(cfg["warn_ratio"], 0.8)
        for key, rel in (
            ("data", "data.json"),
            ("members_file", "members.txt"),
            ("rules", "rules.json"),
            ("backup_dir", "backup"),
            ("log_dir", "logs"),
        ):
            with self.subTest(key=key):
                self.assertEqual(cfg[key], os.path.join(self.tmp.name, rel))

    def test_load_partial_and_nested_override_preserves_default(self):
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
        self.assertIsNone(config.DEFAULT["budget"]["monthly"])
        self.assertIsNone(config.DEFAULT["dues"]["monthly"])

    def test_load_keeps_absolute_path(self):
        abs_data = os.path.join(self.tmp.name, "custom_sub", "data.json")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump({"data": abs_data}, f)
        cfg = config.load(self.cfg_path)
        self.assertEqual(cfg["data"], abs_data)

    def test_load_example_config(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        example_path = os.path.join(repo_root, "config.example.json")
        if not os.path.exists(example_path):
            self.skipTest("config.example.json 없음")
        cfg = config.load(example_path)
        self.assertEqual(cfg["treasurer"], "김민수")
        self.assertEqual(cfg["budget"]["monthly"], 1500000)
        self.assertEqual(cfg["dues"]["monthly"], 20000)
        for key in config.PATH_KEYS:
            with self.subTest(key=key):
                self.assertTrue(os.path.isabs(cfg[key]))

    def test_load_invalid_json_raises_value_error(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("{broken json")
        with self.assertRaises(ValueError) as cm:
            config.load(self.cfg_path)
        self.assertIn("1번째 줄", str(cm.exception))

    def test_load_non_dict_json_raises_value_error(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(list((1, 2, 3)), f)
        with self.assertRaises(ValueError):
            config.load(self.cfg_path)

    def test_load_non_dict_section_raises_value_error(self):
        for payload, key in (({"budget": 5}, "budget"), ({"dues": "x"}, "dues")):
            with self.subTest(key=key):
                with open(self.cfg_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                with self.assertRaises(ValueError) as cm:
                    config.load(self.cfg_path)
                self.assertIn(f"({key})", str(cm.exception))

    def test_load_invalid_path_values_raise_value_error(self):
        for payload, key in (({"data": None}, "data"), ({"log_dir": ""}, "log_dir"), ({"rules": 5}, "rules")):
            with self.subTest(key=key):
                with open(self.cfg_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                with self.assertRaises(ValueError) as cm:
                    config.load(self.cfg_path)
                self.assertIn(f"({key})", str(cm.exception))

    def test_save_default_and_duplicate_error(self):
        config.save_default(self.cfg_path)
        with open(self.cfg_path, encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved, config.DEFAULT)
        with self.assertRaises(FileExistsError):
            config.save_default(self.cfg_path)


if __name__ == "__main__":
    unittest.main()
