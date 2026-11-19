"""기능 4 정산 테스트. 공통 함수 queries.is_locked 와 자료 항목 locks 포함."""

import json

from helpers import StoreCase

from moim.common import queries
from moim.common.store import Store


class IsLockedTest(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["locks"].append({"start": "2026-11-01", "end": "2026-11-30"})

    def test_empty_has_locks(self):
        self.assertEqual(Store(self.path("new.json")).load().data["locks"], [])

    def test_no_locks_is_false(self):
        self.store.data["locks"] = []
        self.assertFalse(queries.is_locked(self.store, "2026-11-15"))

    def test_start_and_end_included(self):
        # 규약 6: 확정 기간의 시작일·끝일도 잠긴다
        self.assertTrue(queries.is_locked(self.store, "2026-11-01"))
        self.assertTrue(queries.is_locked(self.store, "2026-11-30"))

    def test_outside_period(self):
        self.assertFalse(queries.is_locked(self.store, "2026-10-31"))
        self.assertFalse(queries.is_locked(self.store, "2026-12-01"))

    def test_any_of_several_locks(self):
        self.store.data["locks"].append({"start": "2027-01-01", "end": "2027-01-31"})
        self.assertTrue(queries.is_locked(self.store, "2027-01-31"))
        self.assertFalse(queries.is_locked(self.store, "2026-12-15"))

    def test_old_file_without_locks(self):
        # locks 가 없는 옛 자료 파일도 읽으면 기본값 [] 로 채워져 False
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1}, f)
        old = Store(self.path("old.json")).load()
        self.assertFalse(queries.is_locked(old, "2026-11-15"))

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            queries.is_locked(self.store, "2026-11-31")