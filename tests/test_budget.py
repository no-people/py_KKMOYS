import datetime as dt
import unittest
from helpers import NAMES, StoreCase
from moim.common import queries

KIM, LEE, PARK = NAMES


class TestIsMemberActive(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": KIM, "joined": "2026-09-01", "left": None},
            {"name": PARK, "joined": "2026-09-01", "left": "2026-11-15"},
        ]

    def test_boundaries_from_spec(self):
        # 규격 3-6 예시: 가입 전날(False), 가입 당일(True), 탈퇴 당일(True), 탈퇴 다음 날(False)
        self.assertFalse(queries.is_member_active(self.store, PARK, "2026-08-31"))
        self.assertTrue(queries.is_member_active(self.store, PARK, "2026-09-01"))
        self.assertTrue(queries.is_member_active(self.store, PARK, "2026-11-15"))
        self.assertFalse(queries.is_member_active(self.store, PARK, "2026-11-16"))

    def test_unknown_and_active_member(self):
        self.assertFalse(queries.is_member_active(self.store, "없는사람", "2026-11-10"))
        self.assertTrue(queries.is_member_active(self.store, KIM, dt.date(2026, 11, 10)))


if __name__ == "__main__":
    unittest.main()
