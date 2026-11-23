"""통합 시나리오 테스트(팀 공동 작업, 담당: 강동휘). 역할분담_작업순서.md 6장.

한 달치 연습 자료(tools/gen_data.py)로 명령을 처음부터 끝까지 이어서 실행하고,
보고서·정산·내보내기의 합계와 규약 값이 기능끼리 같은지 확인한다.
아직 만들지 않은 명령·기능은 건너뜀(skipped)으로 표시해 check 가 깨지지 않게 한다.
"""

import contextlib
import csv
import io
import json
import os
import subprocess
import sys
import unittest

from helpers import StoreCase

from moim import cli
from moim.common import ledger, queries
from moim.common.rules import UNCATEGORIZED

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONTH, START, END = "2026-11", "2026-11-01", "2026-11-30"

# 기능 파일·명령 뼈대가 아직 구현 전일 때 나오는 문구
NOT_IMPLEMENTED = ("아직 만들지 않은 명령입니다", "아직 구현되지 않은 기능입니다")
# 6장 시나리오 명령 중 아직 main 에 없는 것. 이 명령의 "invalid choice" 만 건너뛰고, 그 밖의 이름 오류는 실패시킨다.
# 이름은 각 담당 브랜치 기준(report: 민기슬 feat/report, io: 오재원 feat/io-export-basic). 병합되면 여기서 뺀다.
PENDING = {("init",), ("member", "load"), ("exp", "import-lines"), ("report", "month"),
           ("io", "export-csv"), ("io", "verify")}


class ScenarioCase(StoreCase):
    """연습 자료를 만들고, 설정 파일을 쓰고, cli.main 을 실행하는 도우미."""

    def setUp(self):
        super().setUp()
        self.sample = self.path("sample")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_data.py"), self.sample,
                        "--month", MONTH], check=True, stdout=subprocess.DEVNULL)
        self.config = self.path("config.json")
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path, "rules": self.cfg["rules"], "treasurer": "김민수",
                       "members_file": os.path.join(self.sample, "members.txt")}, f, ensure_ascii=False)

    def run_cli(self, *argv):
        """명령을 실행해 (종료 코드, 출력 줄 목록, 오류 문자열)을 돌려준다."""
        lines, err = [], io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["--config", self.config, *argv], out=lines.append)
        return code, lines, err.getvalue()

    def pending_reason(self, argv, lines, err):
        """아직 구현 전이라 건너뛸 명령이면 실제 오류 문장을, 아니면 None 을 돌려준다."""
        text = "\n".join(lines) + err
        if any(word in text for word in NOT_IMPLEMENTED):
            return text.strip().splitlines()[-1]
        if "invalid choice" in err and (tuple(argv[:1]) in PENDING or tuple(argv[:2]) in PENDING):
            return err.strip()
        return None

    def cli_ok(self, *argv):
        """명령이 성공해야 한다. 아직 구현 전인 명령이면 그 오류 문장으로 건너뜀."""
        code, lines, err = self.run_cli(*argv)
        reason = self.pending_reason(argv, lines, err)
        if reason:
            self.skipTest(f"{' '.join(argv)}: {reason}")
        self.assertEqual(code, 0, f"{' '.join(argv)} 실패: {err}")
        return lines

    def step(self, *argv):
        """시나리오 한 단계. 구현 전이면 self.skipped 에 적고 None, 성공하면 출력 줄 목록."""
        code, lines, err = self.run_cli(*argv)
        reason = self.pending_reason(argv, lines, err)
        if reason:
            self.skipped.append(f"{' '.join(argv[:2])} ({reason})")
            return None
        self.assertEqual(code, 0, f"{' '.join(argv)} 실패: {err}")
        return lines

    def sample_rows(self):
        with open(os.path.join(self.sample, "expenses.csv"), encoding="utf-8") as f:
            return list(csv.reader(f))

    def insert_sample(self):
        """exp import-lines 대신 공통 함수로 명부·지출을 넣는다(명령이 생기기 전까지 쓰는 길)."""
        with open(os.path.join(self.sample, "members.txt"), encoding="utf-8") as f:
            self.store.data["members"] = [{"name": n, "joined": j, "left": None}
                                          for n, j in (line.strip().split(",") for line in f if line.strip())]
        for day, payer, amount, members, memo in self.sample_rows():
            ledger.insert(self.store, day, payer, amount, members.split(";"), memo)
        self.store.save()


class SampleDataTest(ScenarioCase):
    """0단계: 연습 자료가 시나리오에 쓸 모양으로 만들어지는가."""

    def test_files_and_rows(self):
        for name in ("members.txt", "expenses.csv", "bank_202611.csv"):
            self.assertTrue(os.path.exists(os.path.join(self.sample, name)), name)
        rows = self.sample_rows()
        self.assertEqual(len(rows), 40)
        self.assertTrue(all(START <= r[0] <= END for r in rows))


class FullScenarioTest(ScenarioCase):
    """6장 순서: (init) → member load → exp import-lines → cat → report → settle → budget import-bank → io.
    구현 전인 단계는 적어 두고 다음 단계로 넘어가, 된 단계는 모두 실행한다. 마지막에 건너뛴 단계를 알린다.
    init 은 setUp 이 config.json 을 직접 쓰므로 구현되기 전까지 뺀다(11/30 전체 통과 목표)."""

    def test_full_flow(self):
        self.skipped = []
        loaded = self.step("member", "load") is not None
        loaded = self.step("exp", "import-lines", os.path.join(self.sample, "expenses.csv")) is not None and loaded
        if not loaded:
            self.insert_sample()   # 명령이 생기기 전까지는 공통 함수로 명부·지출을 넣는다
        self.step("cat", "add", "식비", "--keywords", "저녁", "점심", "김밥", "간식", "음료")
        self.step("cat", "apply")
        self.step("report", "month", "--month", MONTH)
        self.step("settle", "balance", "--month", MONTH)
        self.step("budget", "import-bank", os.path.join(self.sample, "bank_202611.csv"))
        out = self.path("out.csv")
        if self.step("io", "export-csv", out) is not None:
            self.step("io", "verify", out)
        if self.skipped:
            self.skipTest("건너뛴 단계: " + " / ".join(self.skipped))


class CategoryTotalsMatchTest(ScenarioCase):
    """분류 단계 합계: cat 명령 결과와 공통 함수(category_totals·period_total)가 같은가."""

    def setUp(self):
        super().setUp()
        self.insert_sample()
        self.cli_ok("cat", "add", "식비", "--keywords", "저녁", "점심", "김밥")
        self.cli_ok("cat", "add", "장소", "--keywords", "대관")
        self.cli_ok("cat", "apply")
        self.store.load()   # cli 가 저장한 파일을 다시 읽는다

    def test_amount_sum_equals_period_total(self):
        totals = queries.category_totals(self.store, START, END)
        self.assertEqual(sum(v["amount"] for v in totals.values()),
                         queries.period_total(self.store, START, END))
        self.assertEqual(sum(v["count"] for v in totals.values()), 40)

    def test_uncat_count_matches_totals(self):
        # cat uncat 의 마지막 줄 "미분류 N건" 과 category_totals 의 미분류 건수가 같다(규약 5)
        last = self.cli_ok("cat", "uncat")[-1]
        count = queries.category_totals(self.store, START, END).get(UNCATEGORIZED, {"count": 0})["count"]
        self.assertEqual(last, f"{UNCATEGORIZED} {count}건")


class RuleValuesTest(unittest.TestCase):
    """규약 값이 모든 기능에서 같게 나오는지(역할분담 6장). 각 기능이 들어오는 대로 채운다."""

    def test_half_up_rounding(self):
        self.skipTest("11/30 채움: 사사오입(규약 1) — 보고서·정산·내보내기 금액 비교")

    def test_remainder_one_won(self):
        self.skipTest("11/30 채움: 나머지 1원(규약 2) — 정산 결과와 money.split 비교")

    def test_period_ends_included(self):
        self.skipTest("11/30 채움: 기간 양 끝 포함(규약 3) — report·settle·io 의 기간 합계 비교")

    def test_member_left_day(self):
        self.skipTest("11/30 채움: 탈퇴일 당일까지 회원(규약 4) — member leave 뒤 정산·회비")

    def test_locked_period(self):
        self.skipTest("11/30 채움: 정산 확정 기간(규약 6) — 확정 뒤 cat apply·exp 수정이 막히는지")


if __name__ == "__main__":
    unittest.main()
