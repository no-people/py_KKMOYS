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

# 명령이 아직 없을 때 나오는 안내(통합 실행 틀·명령 묶음 뼈대의 문구)
NOT_READY = ("아직 만들지 않은 명령입니다", "아직 구현되지 않은 기능입니다", "invalid choice")


class ScenarioCase(StoreCase):
    """연습 자료를 만들고, 설정 파일을 쓰고, cli.main 을 실행하는 도우미."""

    def setUp(self):
        super().setUp()
        self.sample = self.path("sample")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_data.py"), self.sample,
                        "--month", MONTH], check=True, stdout=subprocess.DEVNULL)
        self.config = self.path("config.json")
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path, "rules": self.cfg["rules"],
                       "members_file": os.path.join(self.sample, "members.txt")}, f, ensure_ascii=False)

    def run_cli(self, *argv):
        """명령을 실행해 (출력 줄 목록, 오류 문자열)을 돌려준다. 아직 없는 명령이면 건너뜀."""
        lines, err = [], io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["--config", self.config, *argv], out=lines.append)
        text = "\n".join(lines) + err.getvalue()
        if any(word in text for word in NOT_READY):
            self.skipTest(f"아직 안 된 명령: {' '.join(argv)}")
        self.assertEqual(code, 0, f"{' '.join(argv)} 실패: {err.getvalue()}")
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
    """6장 순서: init → member load → exp import-lines → cat → report → settle → budget import-bank → io.
    앞 단계가 아직 없으면 그 자리에서 건너뜀으로 끝난다(11/30 전체 통과 목표)."""

    def test_full_flow(self):
        self.run_cli("init")
        self.run_cli("member", "load")
        self.run_cli("exp", "import-lines", os.path.join(self.sample, "expenses.csv"))
        self.run_cli("cat", "add", "식비", "--keywords", "저녁", "점심", "김밥", "간식", "음료")
        self.run_cli("cat", "apply")
        self.run_cli("report", "month", "--month", MONTH)
        self.run_cli("settle", "show", "--month", MONTH)
        self.run_cli("budget", "import-bank", os.path.join(self.sample, "bank_202611.csv"))
        self.run_cli("io", "export-csv", self.path("out.csv"))
        self.run_cli("io", "verify", self.path("out.csv"))


class CategoryTotalsMatchTest(ScenarioCase):
    """분류 단계 합계: cat 명령 결과와 공통 함수(category_totals·period_total)가 같은가."""

    def setUp(self):
        super().setUp()
        self.insert_sample()
        self.run_cli("cat", "add", "식비", "--keywords", "저녁", "점심", "김밥")
        self.run_cli("cat", "add", "장소", "--keywords", "대관")
        self.run_cli("cat", "apply")
        self.store.load()   # cli 가 저장한 파일을 다시 읽는다

    def test_amount_sum_equals_period_total(self):
        totals = queries.category_totals(self.store, START, END)
        self.assertEqual(sum(v["amount"] for v in totals.values()),
                         queries.period_total(self.store, START, END))
        self.assertEqual(sum(v["count"] for v in totals.values()), 40)

    def test_uncat_count_matches_totals(self):
        # cat uncat 의 마지막 줄 "미분류 N건" 과 category_totals 의 미분류 건수가 같다(규약 5)
        last = self.run_cli("cat", "uncat")[-1]
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
