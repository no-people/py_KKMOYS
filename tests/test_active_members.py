"""공통모듈 규격 3-7: 회원 기간 판단 재사용, 명부 순서 유지."""
import copy
import datetime as dt
from unittest.mock import patch

from helpers import NAMES, StoreCase
from moim.common import queries

KIM, LEE, PARK = NAMES


class TestActiveMembers(StoreCase):
    def setUp(self):
        super().setUp()
        self.store.data["members"] = [
            {"name": LEE, "joined": "2026-09-01", "left": None},
            {"name": PARK, "joined": "2026-09-01", "left": "2026-11-15"},
            {"name": KIM, "joined": "2026-11-15", "left": None},
        ]

    def test_join_and_leave_day_in_roster_order(self):
        self.assertEqual(queries.active_members(self.store, "2026-11-15"), [LEE, PARK, KIM])

    def test_before_join_and_after_leave(self):
        self.assertEqual(queries.active_members(self.store, "2026-11-14"), [LEE, PARK])
        self.assertEqual(queries.active_members(self.store, "2026-11-16"), [LEE, KIM])

    def test_date_and_datetime_inputs(self):
        self.assertEqual(queries.active_members(self.store, dt.date(2026, 11, 15)), [LEE, PARK, KIM])
        self.assertEqual(
            queries.active_members(self.store, dt.datetime(2026, 11, 16, 23, 59)), [LEE, KIM]
        )

    def test_empty_roster_and_no_active_members(self):
        self.assertEqual(queries.active_members(self.store, "2026-08-31"), [])
        self.store.data["members"] = []
        self.assertEqual(queries.active_members(self.store, "2026-11-15"), [])

    def test_old_roster_without_leave_key(self):
        self.store.data["members"] = [{"name": KIM, "joined": "2026-09-01"}]
        self.assertEqual(queries.active_members(self.store, "2026-11-15"), [KIM])

    def test_query_does_not_modify_store_and_returns_new_list(self):
        before = copy.deepcopy(self.store.data)
        result = queries.active_members(self.store, "2026-11-15")
        result.clear()
        self.assertEqual(self.store.data, before)
        self.assertEqual(queries.active_members(self.store, "2026-11-15"), [LEE, PARK, KIM])

    def test_uses_shared_member_predicate(self):
        with patch.object(queries, "is_member_active", side_effect=[False, True, False]) as active:
            self.assertEqual(queries.active_members(self.store, "2026-11-15"), [PARK])
        self.assertEqual([call.args[1:] for call in active.call_args_list], [
            (LEE, "2026-11-15"), (PARK, "2026-11-15"), (KIM, "2026-11-15")])
