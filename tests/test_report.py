import os
import tempfile
import unittest
from moim.common import textfmt
from moim.common.store import Store


class TestExpensesIn(unittest.TestCase):
    def test_expenses_in_boundaries_and_deleted(self):
        from moim.common import queries
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(os.path.join(tmpdir, "data.json"))
            store.data["expenses"] = [
                {"id": 2, "date": "2026-11-10", "amount": 10000},
                {"id": 1, "date": "2026-11-10", "amount": 20000},
                {"id": 3, "date": "2026-11-01", "amount": 5000},
                {"id": 4, "date": "2026-11-30", "amount": 8000},
                {"id": 5, "date": "2026-12-01", "amount": 3000},
                {"id": 6, "date": "2026-11-15", "amount": 7000, "deleted": True},
            ]

            res = queries.expenses_in(store, "2026-11-01", "2026-11-30")
            self.assertEqual([e["id"] for e in res], [3, 1, 2, 4])

            res_all = queries.expenses_in(store, "2026-11-01", "2026-11-30", include_deleted=True)
            self.assertEqual([e["id"] for e in res_all], [3, 1, 2, 6, 4])


class TestTextfmtTable(unittest.TestCase):
    def test_table_spec_example(self):
        result = textfmt.table(
            ["이름", "낸 돈"],
            [["김민수", 9000], ["이서연", 6000]],
            total=["합계", 15000],
            numeric={1},
        )
        expected = "\n".join([
            "이름    낸 돈",
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
            "a",
            "-----",
            "1,234",
        ])
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()