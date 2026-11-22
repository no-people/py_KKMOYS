import os
import tempfile
import unittest

from moim.common import queries
from moim.common.store import Store


class TestExpensesIn(unittest.TestCase):
    def test_expenses_in_boundaries_and_deleted(self):
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

            # 1. 시작일(11-01)·끝일(11-30) 포함, 삭제 제외, 날짜순·번호순 정렬 확인
            res = queries.expenses_in(store, "2026-11-01", "2026-11-30")
            self.assertEqual([e["id"] for e in res], [3, 1, 2, 4])

            # 2. include_deleted=True 일 때 삭제 표시 지출 포함 확인
            res_all = queries.expenses_in(store, "2026-11-01", "2026-11-30", include_deleted=True)
            self.assertEqual([e["id"] for e in res_all], [3, 1, 2, 6, 4])

    def test_expenses_in_empty_store_invalid_date_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = Store(os.path.join(tmpdir, "data.json"))
            store.data["expenses"] = []

            with self.assertRaises(ValueError):
                queries.expenses_in(store, "2026-13-01", "2026-11-30")


if __name__ == "__main__":
    unittest.main()