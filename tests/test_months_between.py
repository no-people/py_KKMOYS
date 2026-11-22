"""공통모듈 규격 2-2와 규약 3: 시작·끝 달 포함, 연도 경계."""
import unittest

import helpers  # noqa: F401 — 프로젝트 경로를 설정한다.
from moim.common import dates


class TestMonthsBetween(unittest.TestCase):
    def test_cross_year_example(self):
        self.assertEqual(
            dates.months_between((2026, 11), (2027, 2)),
            [(2026, 11), (2026, 12), (2027, 1), (2027, 2)],
        )

    def test_same_month_is_included(self):
        self.assertEqual(dates.months_between((2026, 11), (2026, 11)), [(2026, 11)])

    def test_reversed_period_is_rejected(self):
        for start, end in [((2026, 12), (2026, 11)), ((2027, 1), (2026, 12))]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                dates.months_between(start, end)

    def test_month_list_includes_february(self):
        self.assertEqual(
            dates.months_between((2028, 1), (2028, 3)),
            [(2028, 1), (2028, 2), (2028, 3)],
        )

    def test_month_order_and_count_across_two_years(self):
        expected = [(2025, 12)] + [(2026, m) for m in range(1, 13)] + [(2027, 1)]
        self.assertEqual(dates.months_between((2025, 12), (2027, 1)), expected)

    def test_invalid_month_is_rejected(self):
        for start, end in [((2026, 0), (2026, 2)), ((2026, 1), (2026, 13))]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                dates.months_between(start, end)

    def test_last_supported_month_does_not_advance_past_end(self):
        self.assertEqual(dates.months_between((9999, 12), (9999, 12)), [(9999, 12)])

    def test_wrong_input_types_and_shapes_have_korean_value_error(self):
        for value in ["2026-11", [2026, 11], None, (2026,), (2026, 11, 1),
                      (2026, "11"), (True, 11), (2026, 11.0)]:
            for start, end in [(value, (2026, 12)), ((2026, 1), value)]:
                with self.subTest(start=start, end=end):
                    with self.assertRaisesRegex(ValueError, "정수 튜플"):
                        dates.months_between(start, end)

    def test_invalid_calendar_values_have_korean_value_error(self):
        for value in [(0, 11), (10000, 1), (2026, 0), (2026, 13)]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "실제 있는"):
                dates.months_between((2026, 1), value)
