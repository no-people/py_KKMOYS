"""기능 1 ledger.insert 테스트 — 공통모듈_함수규격.md 4-3, 규약 4·6·7 경계값."""

import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import NAMES, StoreCase  # noqa: E402
from moim.common.ledger import insert  # noqa: E402
from moim.common.store import Store  # noqa: E402

KIM, LEE, PARK = NAMES


class InsertCase(StoreCase):
    def lock(self, start="2026-11-01", end="2026-11-30"):
        self.store.data["locks"].append({"start": start, "end": end})

    def assert_nothing_added(self):
        self.assertEqual(self.store.data["expenses"], [])
        self.assertEqual(self.store.data["history"], [])
        self.assertEqual(self.store.data["next_id"], 1)


class TestAdd(InsertCase):
    def test_spec_example(self):
        """규격 4-3 예(기본 테스트 F1 test_add)·0장 지출 형식과 키·값이 모두 같아야 한다."""
        e = insert(self.store, "2026-11-12", KIM, "36,000", list(NAMES), memo="회의 후 저녁")
        self.assertEqual(e, {"id": 1, "date": "2026-11-12", "payer": KIM, "amount": 36000,
                             "members": list(NAMES), "weights": None, "category": None,
                             "memo": "회의 후 저녁", "deleted": False, "recurring_id": None,
                             "category_fixed": False})
        self.assertIs(self.store.data["expenses"][-1], e)

    def test_ids_increase(self):
        ids = [insert(self.store, "2026-11-12", KIM, 1000, [KIM])["id"] for _ in range(3)]
        self.assertEqual(ids, [1, 2, 3])
        self.assertEqual(self.store.data["next_id"], 4)

    def test_date_stored_as_yyyy_mm_dd(self):
        self.assertEqual(insert(self.store, "2026-11-1", KIM, 1000, [KIM])["date"], "2026-11-01")
        self.assertEqual(insert(self.store, dt.date(2026, 11, 2), KIM, 1000, [KIM])["date"], "2026-11-02")

    def test_tuple_members_stored_as_list(self):
        self.assertEqual(insert(self.store, "2026-11-12", KIM, 2000, (KIM, LEE))["members"], [KIM, LEE])

    def test_category_given_not_fixed(self):
        """규격 0장: 분류를 넣어도 category_fixed 는 False(고정은 set_category 만)."""
        e = insert(self.store, "2026-11-12", KIM, 9000, [KIM], category="식비")
        self.assertEqual((e["category"], e["category_fixed"]), ("식비", False))
        self.assertIs(self.store.data["history"][-1]["after"]["category_fixed"], False)

    def test_extra_fields_and_action(self):
        """기능 4·5·6 이 넘기는 action·recurring_id·category·weights 가 그대로 남아야 한다."""
        e = insert(self.store, "2026-11-12", KIM, 3000, [KIM, LEE], memo="정기 대관료",
                   weights={KIM: 2, LEE: 1}, category="장소", recurring_id=7, action="recurring")
        self.assertEqual((e["weights"], e["category"], e["recurring_id"]), ({KIM: 2, LEE: 1}, "장소", 7))
        self.assertEqual(self.store.data["history"][-1]["action"], "recurring")
        for action in ("bank", "import"):
            insert(self.store, "2026-11-12", KIM, 1000, [KIM], action=action)
            self.assertEqual(self.store.data["history"][-1]["action"], action)

    def test_memo_stored_as_str(self):
        self.assertEqual(insert(self.store, "2026-11-12", KIM, 1000, [KIM], memo=123)["memo"], "123")
        self.assertEqual(insert(self.store, "2026-11-12", KIM, 1000, [KIM], memo=None)["memo"], "")

    def test_inputs_copied(self):
        """넘긴 members·weights 를 나중에 고쳐도 저장된 지출은 바뀌지 않아야 한다."""
        members, weights = [KIM, LEE], {KIM: 1, LEE: 1}
        e = insert(self.store, "2026-11-12", KIM, 2000, members, weights=weights)
        members.append(PARK)
        weights[KIM] = 9
        self.assertEqual((e["members"], e["weights"]), ([KIM, LEE], {KIM: 1, LEE: 1}))


class TestHistoryAndSave(InsertCase):
    def test_history_add(self):
        e = insert(self.store, "2026-11-12", KIM, 1000, [KIM])
        h = self.store.data["history"]
        self.assertEqual(len(h), 1)
        self.assertEqual((h[0]["id"], h[0]["action"], h[0]["before"], h[0]["after"]), (1, "add", None, e))
        e["amount"] = 9999
        self.assertEqual(h[0]["after"]["amount"], 1000)

    def test_record_failure_rolls_back(self):
        """이력을 남기지 못하면 지출도 번호도 남기지 않는다."""
        self.store.data["history"] = "깨진 값"
        with self.assertRaisesRegex(ValueError, "history"):
            insert(self.store, "2026-11-12", KIM, 1000, [KIM])
        self.assertEqual((self.store.data["expenses"], self.store.data["next_id"]), ([], 1))

    def test_does_not_save(self):
        insert(self.store, "2026-11-12", KIM, 1000, [KIM])
        self.assertFalse(os.path.exists(self.store.path))

    def test_saved_by_caller(self):
        """테스트가 save 를 부르면 지출과 이력이 파일에 남는다(규격 4-3)."""
        insert(self.store, "2026-11-12", KIM, 1000, [KIM])
        self.store.save()
        s2 = Store(self.store.path).load()
        self.assertEqual((len(s2.data["expenses"]), len(s2.data["history"]), s2.data["next_id"]), (1, 1, 2))

    def test_old_file_without_locks_and_history(self):
        with open(self.store.path, "w", encoding="utf-8") as f:
            json.dump({"members": self.store.data["members"], "expenses": [], "next_id": 1}, f)
        s2 = Store(self.store.path).load()
        e = insert(s2, "2026-11-12", KIM, 1000, [KIM])
        self.assertEqual((e["id"], len(s2.data["history"])), (1, 1))


class TestRejected(InsertCase):
    def test_locked_start_and_end(self):
        """규약 6: 확정 기간(양 끝 포함)은 거부하고 아무것도 남기지 않는다."""
        self.lock()
        for day in ("2026-11-01", "2026-11-30"):
            with self.subTest(day=day):
                with self.assertRaisesRegex(ValueError, f"^정산이 확정된 기간입니다: {day}$"):
                    insert(self.store, day, KIM, 1000, [KIM])
                self.assert_nothing_added()

    def test_locked_message_uses_stored_date_form(self):
        self.lock()
        with self.assertRaisesRegex(ValueError, "^정산이 확정된 기간입니다: 2026-11-05$"):
            insert(self.store, "2026-11-5", KIM, 1000, [KIM])
        with self.assertRaisesRegex(ValueError, "^정산이 확정된 기간입니다: 2026-11-15$"):
            insert(self.store, dt.date(2026, 11, 15), KIM, 1000, [KIM])

    def test_outside_lock_ok(self):
        self.lock()
        self.assertEqual(insert(self.store, "2026-12-01", KIM, 1000, [KIM])["date"], "2026-12-01")
        self.assertEqual(insert(self.store, "2026-10-31", KIM, 1000, [KIM])["date"], "2026-10-31")

    def test_validate_error_adds_nothing(self):
        for args in (("2026-11-12", KIM, 0, [KIM]), ("2026-11-12", KIM, 1000, []),
                     ("2026-11-31", KIM, 1000, [KIM]), ("2026-11-12", KIM, 1000, ["없는사람"])):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    insert(self.store, *args)
                self.assert_nothing_added()

    def test_left_day_ok_day_after_rejected(self):
        """규약 4: 탈퇴일 당일까지 회원(실제 is_member_active)."""
        self.store.member(PARK)["left"] = "2026-11-15"
        self.assertEqual(insert(self.store, "2026-11-15", KIM, 1000, [PARK])["members"], [PARK])
        with self.assertRaisesRegex(ValueError, "그날 회원이 아닙니다"):
            insert(self.store, "2026-11-16", KIM, 1000, [PARK])
        self.assertEqual(len(self.store.data["expenses"]), 1)


class TestCategory(InsertCase):
    """분류는 str 또는 None(규격 0장·4-3). 앞뒤 공백을 떼고, 그 밖의 값은 아무것도 바꾸지 않고 거부."""

    def test_strip_and_none(self):
        cases = ((" 식비 ", "식비"), ("\t장소\n", "장소"), ("식비", "식비"), (None, None), ("", None), ("   ", None), ("\t\n", None))
        for given, stored in cases:
            e = insert(self.store, "2026-11-12", KIM, 1000, [KIM], category=given)
            self.assertEqual(e["category"], stored, repr(given))
            self.assertEqual(self.store.data["history"][-1]["after"]["category"], stored)

    def test_non_str_rejected_adds_nothing(self):
        for bad in (5, 0, 1.5, True, False, ["식비"], {"식비": 1}, b"food"):
            with self.assertRaises(ValueError) as cm:
                insert(self.store, "2026-11-12", KIM, 1000, [KIM], category=bad)
            self.assertEqual(str(cm.exception), f"분류는 문자열이어야 합니다: {bad!r}")
            self.assert_nothing_added()

    def test_validate_error_comes_first(self):
        with self.assertRaisesRegex(ValueError, "0원 이하 지출은 받지 않습니다"):
            insert(self.store, "2026-11-12", KIM, 0, [KIM], category=5)
        self.assert_nothing_added()


if __name__ == "__main__":
    unittest.main()
