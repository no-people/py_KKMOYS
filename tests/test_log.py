import io
import logging
import os
import pathlib
import re
import tempfile
import unittest
from datetime import date
from unittest import mock
from moim.common import log

LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO (.+)$")


def _clear_handlers():
    logger = logging.getLogger("moim")
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()


class TestGetLogger(unittest.TestCase):
    def setUp(self):
        _clear_handlers()
        self.tmp = tempfile.TemporaryDirectory()
        self.log_dir = os.path.join(self.tmp.name, "logs")
        self.today_file = os.path.join(self.log_dir, date.today().isoformat() + ".log")

    def tearDown(self):
        _clear_handlers()  # 윈도우에서 열린 파일은 지울 수 없으므로 먼저 닫는다
        self.tmp.cleanup()

    def read_lines(self, path=None):
        for h in logging.getLogger("moim").handlers:
            h.flush()
        with open(path or self.today_file, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_returns_moim_logger(self):
        logger = log.get_logger(self.log_dir)
        self.assertEqual(logger.name, "moim")
        self.assertIsInstance(logger, logging.Logger)

    def test_creates_missing_dir_and_dated_file(self):
        self.assertFalse(os.path.exists(self.log_dir))
        log.get_logger(self.log_dir).info("지출 추가 1번 36,000원")
        self.assertTrue(os.path.isdir(self.log_dir))
        self.assertTrue(os.path.isfile(self.today_file))

    def test_creates_nested_dir(self):
        nested = os.path.join(self.log_dir, "a", "b")
        log.get_logger(nested).info("메시지")
        self.assertTrue(os.path.isfile(os.path.join(nested, date.today().isoformat() + ".log")))

    def test_line_format(self):
        log.get_logger(self.log_dir).info("지출 추가 1번 36,000원")
        lines = self.read_lines()
        self.assertEqual(len(lines), 1)
        m = LINE.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(m.group(1), "지출 추가 1번 36,000원")
        file_date = os.path.basename(self.today_file)[:10]
        self.assertTrue(lines[0].startswith(file_date + " "))

    def test_korean_written_as_utf8(self):
        log.get_logger(self.log_dir).info("회비 납부 김민수 20,000원")
        with open(self.today_file, "rb") as f:
            raw = f.read()
        self.assertIn("회비 납부 김민수 20,000원".encode("utf-8"), raw)

    def test_called_twice_writes_one_line(self):
        log.get_logger(self.log_dir)
        logger = log.get_logger(self.log_dir)
        logger.info("한 번만")
        self.assertEqual(len(logger.handlers), 1)
        lines = self.read_lines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].endswith("INFO 한 번만"))

    def test_appends_to_existing_file(self):
        os.makedirs(self.log_dir)
        with open(self.today_file, "w", encoding="utf-8") as f:
            f.write("이전 줄\n")
        log.get_logger(self.log_dir).info("새 줄")
        lines = self.read_lines()
        self.assertEqual(lines[0], "이전 줄")
        self.assertEqual(len(lines), 2)

    def test_other_dir_replaces_handler(self):
        other = os.path.join(self.tmp.name, "other")
        log.get_logger(self.log_dir).info("첫 폴더")
        logger = log.get_logger(other)
        logger.info("둘째 폴더")
        self.assertEqual(len(logger.handlers), 1)
        self.assertEqual(len(self.read_lines()), 1)
        other_file = os.path.join(other, date.today().isoformat() + ".log")
        self.assertEqual(len(self.read_lines(other_file)), 1)
        self.assertTrue(self.read_lines(other_file)[0].endswith("둘째 폴더"))

    def test_date_change_switches_file(self):
        with mock.patch.object(log, "date") as fake_date:
            fake_date.today.return_value = date(2026, 11, 26)
            log.get_logger(self.log_dir).info("26일")
            fake_date.today.return_value = date(2026, 11, 27)
            logger = log.get_logger(self.log_dir)
            logger.info("27일")
        self.assertEqual(len(logger.handlers), 1)
        day26 = self.read_lines(os.path.join(self.log_dir, "2026-11-26.log"))
        day27 = self.read_lines(os.path.join(self.log_dir, "2026-11-27.log"))
        self.assertEqual(len(day26), 1)
        self.assertTrue(day26[0].endswith("INFO 26일"))
        self.assertEqual(len(day27), 1)
        self.assertTrue(day27[0].endswith("INFO 27일"))

    def test_keeps_foreign_handler(self):
        logger = logging.getLogger("moim")
        foreign = logging.StreamHandler(io.StringIO())
        logger.addHandler(foreign)
        log.get_logger(self.log_dir)
        log.get_logger(os.path.join(self.tmp.name, "other"))
        self.assertIn(foreign, logger.handlers)
        self.assertEqual(len(logger.handlers), 2)

    def test_removes_skeleton_null_handler(self):
        logger = logging.getLogger("moim")
        logger.addHandler(logging.NullHandler())
        log.get_logger(self.log_dir)
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.FileHandler)

    def test_accepts_pathlib_path(self):
        logger = log.get_logger(pathlib.Path(self.log_dir))
        logger.info("Path 로 부름")
        self.assertEqual(len(self.read_lines()), 1)

    def test_relative_and_absolute_same_dir_one_handler(self):
        old_cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            log.get_logger("logs")
            logger = log.get_logger(os.path.join(self.tmp.name, "logs"))
            logger.info("한 줄")
        finally:
            os.chdir(old_cwd)
        self.assertEqual(len(logger.handlers), 1)
        self.assertEqual(len(self.read_lines()), 1)

    def test_debug_not_written_info_level(self):
        logger = log.get_logger(self.log_dir)
        logger.debug("안 남음")
        logger.warning("경고 남음")
        lines = self.read_lines()
        self.assertEqual(len(lines), 1)
        self.assertIn(" WARNING 경고 남음", lines[0])


if __name__ == "__main__":
    unittest.main()
