"""통합 실행 틀(moim/cli.py)의 오류 안내: "오류: 이유" 한 줄, 종료 코드 1, 오류 때는 저장하지 않음."""

import contextlib
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
        self.assert_error(self.call("exp"), f"자료 파일 형식이 잘못되었습니다: {self.store.path} (2번째 줄)")

    def test_data_file_wrong_shape(self):
        with open(self.store.path, "w", encoding="utf-8") as f:
            json.dump({"expenses": []}, f)
        self.assert_error(self.call("exp"), "자료 파일에 members 항목이 없습니다")

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
                          f"자료 파일의 글자 인코딩을 읽을 수 없습니다(UTF-8 이어야 합니다): {self.store.path}")

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


class CliLogTest(StoreCase):
    """로그 연결: 자료를 바꾼 명령은 저장 뒤 화면 줄을 INFO 로, 설정을 읽은 뒤 난 오류는 ERROR 로 log_dir/오늘.log 에."""

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


if __name__ == "__main__":
    unittest.main()
