from datetime import date
import os
import tempfile
from types import SimpleNamespace
import unittest

from moim.common import queries, textfmt
from moim.common.store import Store

class TestTextfmtTable(unittest.TestCase):
    def test_table_spec_example(self):
        result = textfmt.table(
            ["이름", "낸 돈"],
            [["김민수", 9000], ["이서연", 6000]],
            total=["합계", 15000],
            numeric={1},
        )
        expected = "\n".join([
            "이름    낸 돈 ",
            "------  ------",
            "김민수   9,000",
            "이서연   6,000",
            "------  ------",
            "합계    15,000",
        ])
        self.assertEqual(result, expected)

    def test_table_without_total_and_numeric(self):
        result = textfmt.table(["항목", "비고"], [["식비", "점심"]])
        expected = "\n".join([
            "항목  비고",
            "----  ----",
            "식비  점심",
        ])
        self.assertEqual(result, expected)

    def test_table_formats_int_even_when_not_in_numeric(self):
        result = textfmt.table(["a"], [[1234]])
        expected = "\n".join([
            "a    ",
            "-----",
            "1,234",
        ])
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()