"""통합 실행 틀(moim/cli.py)의 오류 안내: "오류: 이유" 한 줄, 종료 코드 1, 오류 때는 저장하지 않음."""

import contextlib
import io
import json
import unittest
from unittest import mock

from helpers import StoreCase

from moim import cli
from moim.commands import expenses


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


if __name__ == "__main__":
    unittest.main()
