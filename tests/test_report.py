from datetime import date
import os
import tempfile
from types import SimpleNamespace
import unittest

from moim.common import queries, textfmt
from moim.common.store import Store
from moim.features import report as report_feature


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


class TestPersonPaid(unittest.TestCase):
    def setUp(self):
        self.store = SimpleNamespace(
            data={
                "expenses": [
                    {
                        "id": 1,
                        "date": "2026-11-01",
                        "payer": "민기슬",
                        "amount": 12000,
                        "members": ["민기슬", "강동휘", "오재원"],
                        "deleted": False,
                    },
                    {
                        "id": 2,
                        "date": "2026-11-15",
                        "payer": "강동휘",
                        "amount": 8000,
                        "members": ["민기슬", "강동휘", "오재원", "염승민"],
                    },
                    {
                        "id": 3,
                        "date": "2026-11-30",
                        "payer": "민기슬",
                        "amount": 5000,
                        "members": ["민기슬", "강동휘"],
                        "deleted": False,
                    },
                    {
                        "id": 4,
                        "date": "2026-11-20",
                        "payer": "민기슬",
                        "amount": 99000,
                        "members": ["민기슬"],
                        "deleted": True,
                    },
                    {
                        "id": 5,
                        "date": "2026-11-18",
                        "payer": "손가인",
                        "amount": 40000,
                        "members": ["손가인", "민기슬"],
                        "deleted": True,
                    },
                    {
                        "id": 6,
                        "date": "2026-10-31",
                        "payer": "오재원",
                        "amount": 30000,
                        "members": ["오재원", "민기슬"],
                    },
                    {
                        "id": 7,
                        "date": "2026-12-01",
                        "payer": "염승민",
                        "amount": 25000,
                        "members": ["염승민", "민기슬"],
                    },
                ]
            }
        )

    def test_person_paid_includes_boundaries_and_excludes_deleted(self):
        result = queries.person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result, {"민기슬": 17000, "강동휘": 8000})

    def test_person_paid_with_date_objects(self):
        result = queries.person_paid(self.store, date(2026, 11, 1), date(2026, 11, 30))
        self.assertEqual(result, {"민기슬": 17000, "강동휘": 8000})

    def test_person_paid_spec_example_f3(self):
        f3_store = SimpleNamespace(
            data={
                "expenses": [
                    {"id": 1, "date": "2026-11-12", "payer": "이서연", "amount": 6000},
                    {"id": 2, "date": "2026-11-13", "payer": "김민수", "amount": 9000},
                    {"id": 3, "date": "2026-10-15", "payer": "김민수", "amount": 3000},
                ]
            }
        )
        self.assertEqual(
            queries.person_paid(f3_store, "2026-11-10", "2026-11-20"),
            {"이서연": 6000, "김민수": 9000},
        )

    def test_person_paid_excludes_person_with_only_deleted_expenses(self):
        result = queries.person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertNotIn("손가인", result)

    def test_person_paid_excludes_member_who_did_not_pay(self):
        result = queries.person_paid(self.store, "2026-11-01", "2026-11-30")
        self.assertNotIn("오재원", result)
        self.assertNotIn("염승민", result)

    def test_person_paid_legacy_store_without_expenses_key(self):
        legacy_store = SimpleNamespace(data={})
        self.assertEqual(queries.person_paid(legacy_store, "2026-11-01", "2026-11-30"), {})

    def test_person_paid_empty_when_no_matching_expenses(self):
        result = queries.person_paid(self.store, "2026-01-01", "2026-01-31")
        self.assertEqual(result, {})


class TestEmptyStoreDateValidation(unittest.TestCase):
    def setUp(self):
        self.empty_store = SimpleNamespace(data={"expenses": []})

    def test_expenses_in_empty_store_returns_empty_list(self):
        self.assertEqual(queries.expenses_in(self.empty_store, "2026-11-01", "2026-11-30"), [])

    def test_person_paid_empty_store_returns_empty_dict(self):
        self.assertEqual(queries.person_paid(self.empty_store, "2026-11-01", "2026-11-30"), {})

    def test_invalid_date_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            queries.expenses_in(self.empty_store, "2026/11/01", "2026-11-30")
        with self.assertRaises(ValueError):
            queries.person_paid(self.empty_store, "2026-11-01", "2026-11-31")

    def test_nonexistent_leap_day_raises_value_error(self):
        with self.assertRaises(ValueError):
            queries.expenses_in(self.empty_store, "2026-02-29", "2026-03-01")
        with self.assertRaises(ValueError):
            queries.person_paid(self.empty_store, "2026-02-01", "2026-02-29")

    def test_leap_year_feb_29_is_accepted(self):
        leap_store = SimpleNamespace(
            data={
                "expenses": [
                    {"id": 1, "date": "2028-02-29", "payer": "민기슬", "amount": 4000},
                ]
            }
        )
        expenses = queries.expenses_in(leap_store, "2028-02-29", "2028-02-29")
        self.assertEqual([e["id"] for e in expenses], [1])
        self.assertEqual(
            queries.person_paid(leap_store, "2028-02-29", "2028-02-29"),
            {"민기슬": 4000},
        )


class TestEmptyStoreInvalidDate(unittest.TestCase):
    def test_expenses_in_invalid_start_date_empty_store(self):
        store = SimpleNamespace(data={"expenses": []})
        with self.assertRaises(ValueError):
            queries.expenses_in(store, "2026-13-01", "2026-11-30")

    def test_expenses_in_invalid_end_date_empty_store(self):
        store = SimpleNamespace(data={"expenses": []})
        with self.assertRaises(ValueError):
            queries.expenses_in(store, "2026-11-01", "2026-02-30")

    def test_expenses_in_invalid_date_missing_expenses_key(self):
        store = SimpleNamespace(data={})
        with self.assertRaises(ValueError):
            queries.expenses_in(store, "2026-13-01", "2026-11-30")

    def test_period_total_invalid_date_empty_store(self):
        store = SimpleNamespace(data={"expenses": []})
        with self.assertRaises(ValueError):
            queries.period_total(store, "2026-13-01", "2026-11-30")

    def test_person_paid_invalid_date_empty_store(self):
        store = SimpleNamespace(data={"expenses": []})
        with self.assertRaises(ValueError):
            queries.person_paid(store, "2026-13-01", "2026-11-30")

    def test_category_totals_invalid_date_empty_store(self):
        store = SimpleNamespace(data={"expenses": []})
        with self.assertRaises(ValueError):
            queries.category_totals(store, "2026-13-01", "2026-11-30")


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

    def test_table_empty_rows_keeps_header_and_separator(self):
        result = textfmt.table(["이름", "금액"], [])
        self.assertEqual(result, "이름  금액\n----  ----")

    def test_table_negative_int_comma_right_aligned(self):
        result = textfmt.table(["항목", "금액"], [["환불", -1500], ["식비", 300]], numeric={1})
        expected = "\n".join([
            "항목  금액",
            "----  ------",
            "환불  -1,500",
            "식비     300",
        ])
        self.assertEqual(result, expected)

    def test_table_hangul_counts_two_columns(self):
        result = textfmt.table(["이름", "메모"], [["가나다라", "ab"], ["Kim", "한글"]])
        expected = "\n".join([
            "이름      메모",
            "--------  ----",
            "가나다라  ab",
            "Kim       한글",
        ])
        self.assertEqual(result, expected)

    def test_table_no_trailing_space_or_newline(self):
        result = textfmt.table(["이름", "낸 돈"], [["김민수", 9000]], total=["합계", 9000], numeric={1})
        self.assertFalse(result.endswith("\n"))
        for line in result.split("\n"):
            self.assertEqual(line, line.rstrip())


class TestReportFeature(unittest.TestCase):
    def setUp(self):
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.tmpdir_obj.name, "data.json"))
        self.store.data["expenses"] = [
            {"id": 1, "date": "2026-11-01", "payer": "민기슬", "amount": 5000, "members": ["민기슬", "강동휘"], "category": "식비", "memo": "커피", "deleted": False},
            {"id": 2, "date": "2026-11-12", "payer": "이서연", "amount": 6000, "members": ["이서연", "김민수"], "category": "식비", "memo": "점심", "deleted": False},
            {"id": 3, "date": "2026-11-13", "payer": "김민수", "amount": 9000, "members": ["김민수", "이서연"], "category": "교통", "memo": "지하철", "deleted": False},
            {"id": 4, "date": "2026-11-30", "payer": "민기슬", "amount": 8000, "members": ["민기슬", "오재원"], "category": None, "memo": "간식", "deleted": False},
            {"id": 5, "date": "2026-11-15", "payer": "강동휘", "amount": 50000, "members": ["강동휘"], "category": "식비", "memo": "삭제됨", "deleted": True},
            {"id": 6, "date": "2026-10-20", "payer": "김민수", "amount": 10000, "members": ["김민수", "이서연"], "category": "식비", "memo": "10월", "deleted": False},
            {"id": 7, "date": "2026-12-01", "payer": "민기슬", "amount": 7000, "members": ["민기슬"], "category": "교통", "memo": "12월", "deleted": False},
        ]

    def tearDown(self):
        self.tmpdir_obj.cleanup()

    def test_period_summary_boundaries_and_excludes_deleted(self):
        summary = report_feature.period_summary(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(summary["total"], 28000)
        self.assertEqual(summary["by_category"], {"식비": 11000, "교통": 9000, "미분류": 8000})
        self.assertEqual(summary["by_person"], {"민기슬": 13000, "이서연": 6000, "김민수": 9000})

        empty = report_feature.period_summary(self.store, "2026-01-01", "2026-01-31")
        self.assertEqual(empty, {"total": 0, "by_category": {}, "by_person": {}})

    def test_monthly_totals_and_month_report(self):
        totals = report_feature.monthly_totals(self.store, start_month=(2026, 10), end_month=(2026, 12))
        self.assertEqual(totals, {"2026-10": 10000, "2026-11": 28000, "2026-12": 7000})

        str_month_totals = report_feature.monthly_totals(self.store, start_month="2026-11", end_month="2026-11")
        self.assertEqual(str_month_totals, {"2026-11": 28000})

        text = report_feature.month_report(self.store, month=(2026, 11))
        self.assertIn("2026-11", text)
        self.assertIn("28,000", text)
        self.assertIn("식비", text)
        self.assertIn("민기슬", text)

        str_text = report_feature.month_report(self.store, month="2026-11")
        self.assertIn("2026-11", str_text)
        self.assertIn("28,000", str_text)

    def test_invalid_year_month_raises_value_error(self):
        for bad_ym in [(2026, 0), (2026, 13), ("bad",), True]:
            with self.subTest(bad_ym=bad_ym):
                with self.assertRaises(ValueError):
                    report_feature._to_ym_tuple(bad_ym)


class TestTextfmtBarChart(unittest.TestCase):
    def test_bar_chart_spec_example(self):
        data = {"식비": 10000, "교통": 9000, "미분류": 2000}
        result = textfmt.bar_chart(data, bar_width=10)
        expected = "\n".join([
            "식비    ##########  10,000",
            "교통    #########    9,000",
            "미분류  ##           2,000",
        ])
        self.assertEqual(result, expected)

    def test_bar_chart_half_up_rounding_and_min_one_bar(self):
        data = {"기준": 10000, "반올림": 2500, "버림": 2400, "최소": 1}
        lines = textfmt.bar_chart(data, bar_width=10, char="*").splitlines()
        self.assertEqual(lines[0].count("*"), 10)
        self.assertEqual(lines[1].count("*"), 3)
        self.assertEqual(lines[2].count("*"), 2)
        self.assertEqual(lines[3].count("*"), 1)

    def test_bar_chart_empty_and_all_zero(self):
        self.assertEqual(textfmt.bar_chart({}), "")
        # 모두 0일 때는 막대 없이 값만 출력하며 값 열은 오른쪽 정렬
        self.assertEqual(
            textfmt.bar_chart({"a": 0, "bb": 0}, bar_width=10),
            "a   0\nbb  0",
        )

    def test_bar_chart_single_item_and_width_one(self):
        single = textfmt.bar_chart({"식비": 5000}, bar_width=10, char="#")
        self.assertEqual(single, "식비  ##########  5,000")

        width_one = textfmt.bar_chart({"a": 100, "b": 1, "c": 0}, bar_width=1, char="#")
        self.assertEqual(
            width_one,
            "\n".join([
                "a  #  100",
                "b  #    1",
                "c       0",
            ]),
        )

    def test_bar_chart_negative_values(self):
        # 음수는 0과 동일하게 막대 없이 값만 오른쪽 정렬로 출력
        result = textfmt.bar_chart({"a": -100, "b": 0}, bar_width=10)
        self.assertEqual(result, "a  -100\nb     0")

    def test_bar_chart_invalid_arguments(self):
        with self.assertRaises(ValueError):
            textfmt.bar_chart({"a": 10}, bar_width=0)
        with self.assertRaises(ValueError):
            textfmt.bar_chart({"a": 10}, bar_width=-5)
        with self.assertRaises(ValueError):
            textfmt.bar_chart({"a": 10}, char="")
        with self.assertRaises(ValueError):
            textfmt.bar_chart({"a": 10}, char="##")
        with self.assertRaises(ValueError):
            textfmt.bar_chart({"a": 10}, char="가")


if __name__ == "__main__":
    unittest.main()