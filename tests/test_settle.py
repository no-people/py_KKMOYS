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

    def test_old_file_locks_null(self):
        # "locks": null 인 옛 자료 파일도 TypeError 없이 False (규격 3-10 "locks 가 없으면 False")
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [], "next_id": 1, "locks": None}, f)
        old = Store(self.path("old.json")).load()
        self.assertFalse(queries.is_locked(old, "2026-11-15"))

    def test_locks_not_list_raises(self):
        # 깨진 locks 를 확정 기간 없음으로 넘기지 않는다
        for bad in ({}, "abc", 0, False):
            self.store.data["locks"] = bad
            with self.assertRaisesRegex(ValueError, "locks 형식"):
                queries.is_locked(self.store, "2026-11-15")

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            queries.is_locked(self.store, "2026-11-31")


class WeightsFormatTest(StoreCase):
    """지출 한 건의 weights 항목: {참여자 전원의 이름: 1 이상 정수 비율} 또는 None(균등). 공통모듈_함수규격.md "지출 한 건의 형식"."""

    def _expense(self, eid, weights="없음"):
        e = {"id": eid, "date": "2026-11-12", "payer": "김민수", "amount": 101,
             "members": ["김민수", "이서연", "박지훈"], "category": None, "memo": ""}
        if weights != "없음":
            e["weights"] = weights
        return e

    def test_weights_saved_and_loaded_as_int_dict(self):
        self.store.data["expenses"].append(self._expense(1, {"김민수": 2, "이서연": 1, "박지훈": 1}))
        self.store.save()
        e = Store(self.store.path).load().get_expense(1)
        self.assertEqual(e["weights"], {"김민수": 2, "이서연": 1, "박지훈": 1})
        self.assertTrue(all(type(w) is int for w in e["weights"].values()))

    def test_none_weights_kept_as_none(self):
        self.store.data["expenses"].append(self._expense(1, None))
        self.store.save()
        self.assertIsNone(Store(self.store.path).load().get_expense(1)["weights"])

    def test_old_expense_without_weights_reads_as_none(self):
        # weights 가 생기기 전의 옛 자료 파일: 읽는 쪽은 e.get("weights") 로 None(균등)을 얻는다
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [self._expense(1)], "next_id": 2}, f)
        e = Store(self.path("old.json")).load().get_expense(1)
        self.assertNotIn("weights", e)
        self.assertIsNone(e.get("weights"))
