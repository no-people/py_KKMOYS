"""기능 2 분류 규칙 테스트. 자료 항목 category_fixed 포함."""

import json
import unittest

from helpers import StoreCase

from moim.common import queries
from moim.common.rules import UNCATEGORIZED
from moim.common.store import Store


class CategoryFixedFormatTest(StoreCase):
    """지출 한 건의 category_fixed 항목: bool. 공통모듈_함수규격.md "지출 한 건의 형식"."""

    # 테스트용 지출 한 건을 만든다. fixed 를 주지 않으면 category_fixed 키가 없는 옛 지출
    def _expense(self, eid, fixed="없음"):
        e = {"id": eid, "date": "2026-11-12", "payer": "김민수", "amount": 9000,
             "members": ["김민수", "이서연"], "category": "식비", "memo": "회의 후 저녁"}
        if fixed != "없음":
            e["category_fixed"] = fixed
        return e

    def test_fixed_true_saved_and_loaded(self):
        # 직접 정한 분류(True)가 저장 후 다시 읽어도 bool True 로 남는다
        self.store.data["expenses"].append(self._expense(1, True))
        self.store.save()
        e = Store(self.store.path).load().get_expense(1)
        self.assertIs(e["category_fixed"], True)

    def test_fixed_false_saved_and_loaded(self):
        # 규칙으로 정한 분류(False)도 그대로 남는다
        self.store.data["expenses"].append(self._expense(1, False))
        self.store.save()
        self.assertIs(Store(self.store.path).load().get_expense(1)["category_fixed"], False)

    def test_old_expense_without_fixed_reads_as_false(self):
        # category_fixed 가 생기기 전의 옛 자료 파일: 읽는 쪽은 e.get("category_fixed", False) 로 False 를 얻는다
        with open(self.path("old.json"), "w", encoding="utf-8") as f:
            json.dump({"members": [], "expenses": [self._expense(1)], "next_id": 2}, f)
        e = Store(self.path("old.json")).load().get_expense(1)
        self.assertNotIn("category_fixed", e)
        self.assertFalse(e.get("category_fixed", False))


class CategoryOfTest(unittest.TestCase):
    """queries.category_of — 공통모듈_함수규격.md 3-3, 규약 5."""

    def test_category_kept(self):
        self.assertEqual(queries.category_of({"category": "식비"}), "식비")

    def test_none_empty_missing_is_uncategorized(self):
        # None, 빈 문자열, 키 없음은 모두 "미분류"
        for e in ({"category": None}, {"category": ""}, {}):
            self.assertEqual(queries.category_of(e), UNCATEGORIZED)
        self.assertEqual(UNCATEGORIZED, "미분류")
