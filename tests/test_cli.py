"""통합 실행 틀(moim/cli.py): 오류 안내("오류: 이유" 한 줄, 종료 코드 1, 오류 때는 저장하지 않음),
init(기본 설정 파일), 로그 연결(log_dir/오늘.log), 깨진 자료 파일 복구(Store.recover)와 안내."""

import contextlib
import glob
import io
import json
import logging
import os
import unittest
from datetime import date
from unittest import mock

from helpers import NAMES, StoreCase

from moim import cli
from moim.commands import expenses
from moim.common import config, log
from moim.common.store import Store


class CliErrorTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.config = self.path("config.json")
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": "data.json"}, f)
        # 백업이 없으면 깨진 자료 파일은 복구하지 못하고 이유를 덧붙여 안내한다(CliRecoverTest)
        self.NO_BACKUP = f"복구할 수 있는 정상 백업 파일이 없습니다(백업 폴더: {self.path('backup')})"

    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--config", self.config, *argv])
        return code, out.getvalue(), err.getvalue()

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def assert_error(self, result, reason):
        code, out, err = result
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err, f"오류: {reason}\n")   # 한 줄, 트레이스백 없음

    def test_success_returns_0(self):
        code, out, err = self.call("exp")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_success_saves_when_run_returns_true(self):
        def change(c, args, cfg, store, out):
            store.data["next_id"] = 7
            return True
        with mock.patch.object(expenses, "run", side_effect=change):
            code, _, err = self.call("exp")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(self.read(self.store.path))["next_id"], 7)

    def test_value_error_message_as_is(self):
        # 공통 함수의 ValueError 메시지(규격 0장 오류 약속)를 그대로 보여 준다
        with mock.patch.object(expenses, "run", side_effect=ValueError("0원 이하 지출은 받지 않습니다: 0")):
            self.assert_error(self.call("exp"), "0원 이하 지출은 받지 않습니다: 0")

    def test_error_does_not_save(self):
        def change_then_fail(c, args, cfg, store, out):
            store.data["next_id"] = 99
            raise ValueError("정산이 확정된 기간입니다: 2026-11-12")
        self.store.save()
        before = self.read(self.store.path)
        with mock.patch.object(expenses, "run", side_effect=change_then_fail):
            self.assert_error(self.call("exp"), "정산이 확정된 기간입니다: 2026-11-12")
        self.assertEqual(self.read(self.store.path), before)

    def test_multiline_message_one_line(self):
        with mock.patch.object(expenses, "run", side_effect=ValueError("첫 줄\n둘째 줄")):
            self.assert_error(self.call("exp"), "첫 줄 둘째 줄")

    def test_unknown_command(self):
        code, out, err = self.call("nope")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("오류: 명령 형식이 잘못되었습니다: "))
        self.assertEqual(err.count("\n"), 1)

    def test_missing_command(self):
        code, out, err = self.call()
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("오류: 명령 형식이 잘못되었습니다: "))
        self.assertEqual(err.count("\n"), 1)

    def test_unknown_option_in_group(self):
        # 명령 묶음(하위 파서)의 인자 오류도 ArgParser 를 물려받아 같은 형식이다
        code, out, err = self.call("exp", "--nope")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("오류: 명령 형식이 잘못되었습니다: "))
        self.assertIn("--nope", err)
        self.assertEqual(err.count("\n"), 1)

    def test_help_still_exits_0(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            cli.main(["-h"])
        self.assertEqual(cm.exception.code, 0)

    def test_broken_data_file(self):
        with open(self.store.path, "w", encoding="utf-8") as f:
            f.write('{"members": [\n')
        self.assert_error(self.call("exp"), f"자료 파일 형식이 잘못되었습니다: {self.store.path} (2번째 줄). {self.NO_BACKUP}")

    def test_data_file_wrong_shape(self):
        with open(self.store.path, "w", encoding="utf-8") as f:
            json.dump({"expenses": []}, f)
        self.assert_error(self.call("exp"), f"자료 파일에 members 항목이 없습니다. {self.NO_BACKUP}")

    def test_broken_config_file(self):
        with open(self.config, "w", encoding="utf-8") as f:
            f.write("{")
        # 규격 8-2(config.load 확정)의 문구 "설정 파일 형식이 잘못되었습니다: <경로>" 로 시작하면 된다.
        # 줄 번호는 cli 가 붙이므로 config.load 가 직접 ValueError 를 내게 되면 빠질 수 있다.
        code, out, err = self.call("exp")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err.startswith("오류: 설정 파일 형식이 잘못되었습니다: "), err)
        self.assertIn("config.json", err)
        self.assertEqual(err.count("\n"), 1)

    def test_file_not_found(self):
        missing = self.path("없는파일.csv")
        with mock.patch.object(expenses, "run", side_effect=lambda *a: self.read(missing)):
            self.assert_error(self.call("exp"), f"파일이 없습니다: {missing}")

    def test_os_error_without_filename(self):
        # config.save_default 의 FileExistsError("이미 있습니다: ...") 처럼 파일 이름 없이 메시지만 있는 경우
        with mock.patch.object(expenses, "run", side_effect=FileExistsError("이미 있습니다: config.json")):
            self.assert_error(self.call("exp"), "이미 있습니다: config.json")

    def test_not_implemented(self):
        with mock.patch.object(expenses, "run", side_effect=NotImplementedError):
            self.assert_error(self.call("exp"), "아직 구현되지 않은 기능입니다")
        with mock.patch.object(expenses, "run", side_effect=NotImplementedError("자료 파일 손상 대응 담당이 구현한다")):
            self.assert_error(self.call("exp"), "아직 구현되지 않은 기능입니다: 자료 파일 손상 대응 담당이 구현한다")

    def test_data_file_not_utf8(self):
        with open(self.store.path, "wb") as f:
            f.write('{"members": [], "expenses": [], "memo": "회비"}'.encode("cp949"))
        self.assert_error(self.call("exp"),
                          f"자료 파일의 글자 인코딩을 읽을 수 없습니다(UTF-8 이어야 합니다): {self.store.path}. {self.NO_BACKUP}")

    def test_unicode_error_in_command(self):
        # 명령 안에서 읽은 다른 파일(예: CSV)의 인코딩 오류는 경로 없이 안내한다
        bad = UnicodeDecodeError("utf-8", b"\xc8", 0, 1, "invalid start byte")
        with mock.patch.object(expenses, "run", side_effect=bad):
            self.assert_error(self.call("exp"), "파일의 글자 인코딩을 읽을 수 없습니다(UTF-8 이어야 합니다)")

    def test_bug_is_not_hidden(self):
        # 규격 밖의 예외(코드 버그)는 삼키지 않는다: 트레이스백으로 원인을 찾게 둔다
        with mock.patch.object(expenses, "run", side_effect=KeyError("amount")):
            with self.assertRaises(KeyError):
                self.call("exp")


class InitTest(StoreCase):
    """`init`: 기본 설정 파일(config.DEFAULT)을 --config 경로에 만든다. 이미 있으면 덮어쓰지 않는다."""

    def setUp(self):
        super().setUp()
        self.config = self.path("config.json")

    def call(self, *argv):
        lines, err = [], io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["--config", self.config, *argv], out=lines.append)
        return code, lines, err.getvalue()

    def test_creates_default_config(self):
        code, lines, err = self.call("init")
        self.assertEqual((code, err), (0, ""))
        with open(self.config, encoding="utf-8") as f:
            self.assertEqual(json.load(f), config.DEFAULT)
        self.assertEqual(lines, [f"설정 파일을 만들었습니다: {self.config}",
                                 "모임에 맞게 채울 항목: treasurer(총무), budget.monthly(월 예산), dues.monthly(월 회비)",
                                 "자료 파일(data)은 처음 자료를 저장할 때 만들어집니다"])

    def test_does_not_create_data_file(self):
        self.assertEqual(self.call("init")[0], 0)
        self.assertFalse(os.path.exists(self.path("data.json")))

    def test_existing_config_not_overwritten(self):
        with open(self.config, "w", encoding="utf-8") as f:
            f.write('{"group": "AI 동아리"}')
        code, lines, err = self.call("init")
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(err, f"오류: 이미 있습니다: {self.config}\n")
        with open(self.config, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"group": "AI 동아리"}')

    def test_broken_existing_config_not_read(self):
        # init 은 설정 파일을 읽지 않는다: 깨진 파일이 있어도 형식 오류가 아니라 "이미 있습니다" 로 거부
        with open(self.config, "w", encoding="utf-8") as f:
            f.write("{")
        code, _, err = self.call("init")
        self.assertEqual((code, err), (1, f"오류: 이미 있습니다: {self.config}\n"))

    def test_missing_folder(self):
        folder = os.path.join(self.dir, "없는폴더")
        self.config = os.path.join(folder, "config.json")
        code, lines, err = self.call("init")
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(err, f"오류: 설정 파일을 만들 폴더가 없습니다: {folder}\n")
        self.assertFalse(os.path.exists(folder))

    def test_folder_given_as_config(self):
        # 폴더 자체를 --config 로 주면 덮어쓰지 않고 "이미 있습니다"
        self.config = self.dir
        code, _, err = self.call("init")
        self.assertEqual((code, err), (1, f"오류: 이미 있습니다: {self.dir}\n"))

    def test_config_after_init_is_usage_error(self):
        # --config 는 맨 앞 옵션: init 뒤에 쓰면 형식 오류이고 파일을 만들지 않는다
        other = self.path("other.json")
        code, _, err = self.call("init", "--config", other)
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("오류: 명령 형식이 잘못되었습니다: "), err)
        self.assertIn("--config", err)
        self.assertFalse(os.path.exists(other))
        self.assertFalse(os.path.exists(self.config))

    def test_created_config_works(self):
        # 만든 설정을 config.load 가 그대로 읽고, 그 설정으로 다른 명령이 돈다
        self.assertEqual(self.call("init")[0], 0)
        self.assertEqual(config.load(self.config)["data"], self.path("data.json"))
        code, _, err = self.call("exp", "list")
        self.assertEqual((code, err), (0, ""))

    def test_default_config_path(self):
        # --config 를 안 주면 현재 폴더의 config.json
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            self.assertEqual(cli.main(["init"], out=[].append), 0)
        finally:
            os.chdir(cwd)
        self.assertTrue(os.path.exists(self.config))

    def test_init_in_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["-h"])
        self.assertIn("python -m moim --config <경로> init", " ".join(out.getvalue().split()))   # 도움말 줄바꿈 무시


class LogCase(StoreCase):
    """설정 파일(log_dir=logs)을 쓰고 cli.main 을 실행하며 오늘 로그 파일을 읽는 도우미. 테스트는 없다."""

    def setUp(self):
        super().setUp()
        self.log_dir = self.path("logs")
        self.config = self.path("config.json")
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": "data.json", "log_dir": "logs"}, f)
        self.store.save()
        self.log_file = os.path.join(self.log_dir, date.today().isoformat() + ".log")

    def tearDown(self):
        logger = logging.getLogger(log.LOGGER_NAME)
        for h in list(logger.handlers):
            logger.removeHandler(h)
            with contextlib.suppress(ValueError):   # 쓰기 실패 테스트에서 일부러 닫은 파일
                h.close()
        super().tearDown()

    def call(self, *argv):
        lines, err = [], io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["--config", self.config, *argv], out=lines.append)
        return code, lines, err.getvalue()

    def log_lines(self):
        with open(self.log_file, encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f]

    def assert_log(self, expected):
        # 한 줄 형식: "2026-11-16 17:32:15 INFO 지출 추가 1번 36,000원" (규격 8-1)
        lines = self.log_lines()
        self.assertEqual(len(lines), len(expected), lines)
        for line, (level, msg) in zip(lines, expected):
            self.assertRegex(line, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} " + level + " ")
            self.assertEqual(line.split(" ", 3)[3], msg)


class CliLogTest(LogCase):
    """로그 연결: 자료를 바꾼 명령은 저장 뒤 화면 줄을 INFO 로, 설정을 읽은 뒤 난 오류는 ERROR 로 log_dir/오늘.log 에."""

    def test_change_logged_after_save(self):
        code, lines, err = self.call("exp", "add", "2026-11-12", "김민수", "36000", ";".join(NAMES), "--memo", "저녁")
        self.assertEqual((code, err), (0, ""), err)
        self.assertTrue(lines[0].startswith("지출 추가 1번: "), lines)
        self.assertIn("36,000원", lines[0])   # 금액은 money.fmt 쉼표(규격 8-1 예)
        self.assert_log([("INFO", line) for line in lines])

    def test_lines_appended(self):
        self.call("member", "add", "최유진", "2026-11-01")
        self.call("member", "leave", "최유진", "2026-11-20")
        self.assert_log([("INFO", "명부 추가: 최유진 (가입일 2026-11-01)"),
                         ("INFO", "탈퇴 기록: 최유진 (탈퇴일 2026-11-20, 그날까지 회원)")])

    def test_read_only_not_logged(self):
        code, _, _ = self.call("exp", "list")
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(self.log_dir))   # 빈 로그 파일·폴더도 만들지 않는다
        self.call("member", "add", "최유진", "2026-11-01")   # 같은 설정에서 바꾸는 명령은 남는다
        self.assert_log([("INFO", "명부 추가: 최유진 (가입일 2026-11-01)")])

    def test_error_logged(self):
        code, _, err = self.call("exp", "add", "2026-11-12", "김민수", "0", ";".join(NAMES))
        self.assertEqual(code, 1)
        reason = err[len("오류: "):].rstrip("\n")
        self.assert_log([("ERROR", f"exp add 실패: {reason}")])

    def test_error_saved_nothing_logged_as_error_only(self):
        def change_then_fail(c, args, cfg, store, out):
            out("지출 추가 9번")
            raise ValueError("정산이 확정된 기간입니다: 2026-11-12")
        with mock.patch.object(expenses, "run", side_effect=change_then_fail):
            self.assertEqual(self.call("exp")[0], 1)
        self.assert_log([("ERROR", "exp 실패: 정산이 확정된 기간입니다: 2026-11-12")])

    def test_save_failure_not_logged_as_info(self):
        with mock.patch.object(Store, "save", side_effect=PermissionError(13, "Permission denied", self.store.path)):
            code, _, _ = self.call("member", "add", "최유진", "2026-11-01")
        self.assertEqual(code, 1)
        self.assert_log([("ERROR", f"member add 실패: 파일에 접근할 권한이 없습니다: {self.store.path}")])

    def test_broken_config_not_logged(self):
        with open(self.config, "w", encoding="utf-8") as f:
            f.write("{")
        self.assertEqual(self.call("exp", "list")[0], 1)
        self.assertFalse(os.path.exists(self.log_dir))   # 설정을 못 읽으면 log_dir 를 모른다
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": "data.json", "log_dir": "logs"}, f)
        self.call("member", "add", "최유진", "2026-11-01")   # 같은 설정에서 바꾸는 명령은 남는다
        self.assert_log([("INFO", "명부 추가: 최유진 (가입일 2026-11-01)")])

    def test_broken_data_file_logged(self):
        with open(self.store.path, "w", encoding="utf-8") as f:
            f.write("{")
        code, _, err = self.call("exp", "list")
        self.assertEqual(code, 1)
        reason = err[len("오류: "):].rstrip("\n")
        self.assert_log([("ERROR", f"exp list 실패: {reason}")])

    def test_multiline_output_one_line(self):
        def change(c, args, cfg, store, out):
            out("첫 줄\n둘째 줄")
            return True
        with mock.patch.object(expenses, "run", side_effect=change):
            self.call("exp")
        self.assert_log([("INFO", "첫 줄 둘째 줄")])

    def test_change_without_output(self):
        with mock.patch.object(expenses, "run", return_value=True):
            self.call("exp")
        self.assert_log([("INFO", "exp 저장")])

    def test_log_failure_is_warning_only(self):
        # 로그 폴더 자리에 파일이 있어 로그를 못 남겨도, 저장한 명령은 성공(0)이고 경고 한 줄만
        with open(self.log_dir, "w", encoding="utf-8") as f:
            f.write("")
        code, lines, err = self.call("member", "add", "최유진", "2026-11-01")
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["명부 추가: 최유진 (가입일 2026-11-01)"])
        self.assertTrue(err.startswith("경고: 로그를 남기지 못했습니다: "), err)
        self.assertEqual(err.count("\n"), 1)
        self.store.load()
        self.assertIn("최유진", [m["name"] for m in self.store.data["members"]])

    def test_log_write_failure_is_warning_only(self):
        # 파일을 연 뒤 쓰기가 실패해도(디스크 가득 참 등) 트레이스백 없이 경고 한 줄
        self.call("member", "add", "최유진", "2026-11-01")
        handler = logging.getLogger(log.LOGGER_NAME).handlers[0]
        handler.stream.close()
        code, lines, err = self.call("member", "add", "정하늘", "2026-11-01")
        self.assertEqual((code, lines), (0, ["명부 추가: 정하늘 (가입일 2026-11-01)"]))
        self.assertTrue(err.startswith("경고: 로그를 남기지 못했습니다: "), err)
        self.assertEqual(err.count("\n"), 1)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("handleError", vars(handler))   # 원래대로 되돌렸다

    def test_error_with_log_failure_one_line(self):
        # 명령 오류에 로그 실패가 겹쳐도 표준 오류는 "오류: 이유" 한 줄
        with open(self.log_dir, "w", encoding="utf-8") as f:
            f.write("")
        code, _, err = self.call("exp", "add", "2026-11-12", "김민수", "0", ";".join(NAMES))
        self.assertEqual((code, err), (1, "오류: 0원 이하 지출은 받지 않습니다: 0\n"))
        os.remove(self.log_dir)   # 로그 폴더를 쓸 수 있게 되면 같은 오류가 ERROR 로 남는다
        self.call("exp", "add", "2026-11-12", "김민수", "0", ";".join(NAMES))
        self.assert_log([("ERROR", "exp add 실패: 0원 이하 지출은 받지 않습니다: 0")])

    def test_init_not_logged(self):
        os.remove(self.config)
        self.assertEqual(self.call("init")[0], 0)
        self.assertFalse(os.path.exists(self.log_dir))
        self.call("member", "add", "최유진", "2026-11-01")   # 같은 설정에서 바꾸는 명령은 남는다
        self.assert_log([("INFO", "명부 추가: 최유진 (가입일 2026-11-01)")])


class CliRecoverTest(LogCase):
    """깨진 자료 파일: Store.recover 로 최근 정상 백업을 되살려 저장하고, 경고 한 줄·로그 WARNING 뒤 명령을 이어 실행."""

    def setUp(self):
        super().setUp()
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": "data.json", "log_dir": "logs", "backup_dir": "bk"}, f)
        self.backup_dir = self.path("bk")
        self.call("member", "add", "최유진", "2026-11-01")   # 저장 → 직전 자료(명부 3명)가 bk/ 에 백업됨
        self.backup = Store(self.store.path, self.backup_dir).backups()[-1]
        self.reset_log()

    def reset_log(self):
        logger = logging.getLogger(log.LOGGER_NAME)
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    def break_data(self, text='{"members": [\n'):
        with open(self.store.path, "w", encoding="utf-8") as f:
            f.write(text)

    def broken_files(self):
        return sorted(glob.glob(glob.escape(self.store.path) + ".broken-*"))

    def names(self):
        with open(self.store.path, encoding="utf-8") as f:
            return [m["name"] for m in json.load(f)["members"]]

    def test_backup_dir_from_config(self):
        self.assertEqual(os.path.dirname(self.backup), self.backup_dir)
        self.assertFalse(os.path.exists(self.path("backup")))

    def test_recover_then_run(self):
        self.break_data()
        code, lines, err = self.call("member", "list")
        self.assertEqual(code, 0)
        broken = self.broken_files()
        self.assertEqual(len(broken), 1)
        reason = f"자료 파일 형식이 잘못되었습니다: {self.store.path} (2번째 줄)"
        notice = (f"자료 파일이 깨져 마지막 저장 직전 백업으로 되돌렸습니다: {self.backup} ({reason}). "
                  f"마지막으로 저장한 변경은 빠졌을 수 있으니 확인하십시오. 깨진 파일: {broken[0]}")
        self.assertEqual(err, f"경고: {notice}\n")
        self.assertEqual(self.names(), NAMES)            # 백업 자료가 자료 파일로 저장됨
        self.assertTrue(any("이서연" in line for line in lines))   # 명령은 되살린 자료로 실행
        with open(broken[0], encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"members": [\n')   # 깨진 파일은 그대로 옆에 남김
        self.assert_log([("WARNING", notice)])

    def test_recover_then_change(self):
        self.break_data()
        code, _, _ = self.call("member", "add", "정하늘", "2026-11-01")
        self.assertEqual(code, 0)
        self.assertEqual(self.names(), NAMES + ["정하늘"])
        lines = self.log_lines()
        self.assertEqual([line.split(" ", 3)[2] for line in lines], ["WARNING", "INFO"])

    def test_last_save_missing_after_recover(self):
        # 백업은 저장 직전 자료: 마지막 저장(최유진 추가)은 되살린 자료에 없다. 안내 문장이 이를 알린다
        self.break_data()
        _, _, err = self.call("member", "list")
        self.assertNotIn("최유진", self.names())
        self.assertIn("마지막으로 저장한 변경은 빠졌을 수 있으니 확인하십시오", err)

    def test_recover_then_command_error(self):
        # 복구는 저장되고, 그 뒤 명령 오류는 따로 "오류: 이유" 줄로. 종료 코드 1
        self.break_data()
        code, _, err = self.call("member", "add", "김민수", "2026-11-01")
        self.assertEqual(code, 1)
        warn, error = err.splitlines()
        self.assertTrue(warn.startswith("경고: 자료 파일이 깨져 마지막 저장 직전 백업으로 되돌렸습니다: "), warn)
        self.assertEqual(error, "오류: 이미 명부에 있는 사람입니다: 김민수")
        self.assertEqual(self.names(), NAMES)   # 되살린 자료는 저장되어 있다
        self.assertEqual([line.split(" ", 3)[2] for line in self.log_lines()], ["WARNING", "ERROR"])

    def test_save_failure_after_recover_restores_broken_file(self):
        self.break_data()
        with mock.patch.object(Store, "save", side_effect=OSError(28, "No space left on device", self.store.path)):
            code, lines, err = self.call("member", "list")
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(err, f"오류: 자료 파일 형식이 잘못되었습니다: {self.store.path} (2번째 줄). "
                              f"백업으로 되살린 자료를 저장하지 못해 자료 파일을 그대로 두었습니다: "
                              f"파일을 읽거나 쓸 수 없습니다: {self.store.path} (No space left on device)\n")
        self.assertEqual(self.broken_files(), [])   # 깨진 파일을 제자리로
        with open(self.store.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"members": [\n')
        code, _, err = self.call("member", "list")   # 다음 실행 때 다시 복구한다
        self.assertEqual(code, 0)
        self.assertTrue(err.startswith("경고: "), err)
        self.assertEqual(self.names(), NAMES)

    def test_recover_skips_broken_latest_backup(self):
        # 최신 백업도 깨졌으면 그 전 정상 백업으로 되살리고, 안내에도 그 백업 경로가 나온다
        self.call("member", "add", "정하늘", "2026-11-01")   # 두 번째 백업(명부 4명)
        backups = Store(self.store.path, self.backup_dir).backups()
        self.assertEqual(len(backups), 2)
        with open(backups[-1], "w", encoding="utf-8") as f:
            f.write("{")
        self.break_data()
        code, _, err = self.call("member", "list")
        self.assertEqual(code, 0)
        self.assertTrue(err.startswith(f"경고: 자료 파일이 깨져 마지막 저장 직전 백업으로 되돌렸습니다: {self.backup} ("), err)
        self.assertEqual(self.names(), NAMES)

    def test_recovered_once(self):
        self.break_data()
        self.call("member", "list")
        code, _, err = self.call("member", "list")   # 복구한 뒤에는 멀쩡한 파일
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(self.broken_files()), 1)

    def test_wrong_shape_and_encoding_recovered(self):
        for broken in ('{"expenses": []}', "[]"):
            self.break_data(broken)
            code, _, err = self.call("member", "list")
            self.assertEqual(code, 0)
            self.assertTrue(err.startswith("경고: 자료 파일이 깨져 마지막 저장 직전 백업으로 되돌렸습니다: "), err)
            self.assertEqual(self.names(), NAMES)
        with open(self.store.path, "wb") as f:
            f.write('{"members": [], "expenses": [], "memo": "회비"}'.encode("cp949"))
        code, _, err = self.call("member", "list")
        self.assertEqual(code, 0)
        self.assertIn("UTF-8", err)
        self.assertEqual(self.names(), NAMES)

    def test_no_valid_backup(self):
        for b in Store(self.store.path, self.backup_dir).backups():
            with open(b, "w", encoding="utf-8") as f:
                f.write("{")   # 백업도 깨짐
        self.break_data()
        code, lines, err = self.call("member", "list")
        self.assertEqual((code, lines), (1, []))
        self.assertEqual(err, f"오류: 자료 파일 형식이 잘못되었습니다: {self.store.path} (2번째 줄). "
                              f"복구할 수 있는 정상 백업 파일이 없습니다(백업 폴더: {self.backup_dir})\n")
        self.assertEqual(self.broken_files(), [])   # 깨진 파일은 옮기지 않는다
        with open(self.store.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"members": [\n')
        self.assertEqual([line.split(" ", 3)[2] for line in self.log_lines()], ["ERROR"])

    def test_missing_data_file_not_recovered(self):
        # 자료 파일이 없는 것은 깨진 것이 아니다: 빈 자료로 시작(Store.load)
        os.remove(self.store.path)
        code, _, err = self.call("member", "list")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.broken_files(), [])

    def test_permission_error_not_recovered(self):
        with mock.patch.object(Store, "load", side_effect=PermissionError(13, "Permission denied", self.store.path)):
            code, _, err = self.call("member", "list")
        self.assertEqual((code, err), (1, f"오류: 파일에 접근할 권한이 없습니다: {self.store.path}\n"))
        self.assertEqual(self.broken_files(), [])


if __name__ == "__main__":
    unittest.main()
