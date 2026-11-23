"""기능 2 분류 규칙 테스트. 자료 항목 category_fixed 포함."""

import unittest
from datetime import date

from helpers import StoreCase

from moim.common import queries
from moim.common.rules import UNCATEGORIZED
from moim.common.store import Store
from moim.features import categorize


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

class CategoryOfTest(unittest.TestCase):
    """queries.category_of — 공통모듈_함수규격.md 3-3, 규약 5."""

    def test_category_kept(self):
        self.assertEqual(queries.category_of({"category": "식비"}), "식비")

    def test_none_empty_missing_is_uncategorized(self):
        # None, 빈 문자열, 공백뿐, 키 없음은 모두 "미분류"
        for e in ({"category": None}, {"category": ""}, {"category": " "}, {"category": "  "}, {}):
            with self.subTest(e=e):
                self.assertEqual(queries.category_of(e), UNCATEGORIZED)
        self.assertEqual(UNCATEGORIZED, "미분류")

    def test_surrounding_spaces_stripped(self):
        # 앞뒤 공백은 떼서 돌려준다(" 식비 " 와 "식비" 가 같은 분류)
        self.assertEqual(queries.category_of({"category": " 식비 "}), "식비")

    def test_non_string_category_raises(self):
        # 문자열이 아닌 값은 번호를 붙인 ValueError (규격 0장 오류 약속)
        for bad in (5, ["식비"], True, 3.0, False, 0, []):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "7번 지출의 분류 형식"):
                    queries.category_of({"id": 7, "category": bad})

    def test_fixed_does_not_change_category(self):
        # category_fixed 는 다시 분류할 때만 쓰고, 분류 이름에는 영향이 없다
        for fixed in (True, False):
            with self.subTest(fixed=fixed):
                self.assertEqual(queries.category_of({"category": "식비", "category_fixed": fixed}), "식비")
                self.assertEqual(queries.category_of({"category": None, "category_fixed": fixed}), UNCATEGORIZED)


class CategoryTotalsTest(StoreCase):
    """queries.category_totals — 공통모듈_함수규격.md 3-4."""

    # 지출 dict 를 직접 넣는다(분류 이름·삭제 표시를 마음대로 정하려고)
    def _add(self, eid, day, amount, category=None, deleted=False):
        self.store.data["expenses"].append(
            {"id": eid, "date": day, "payer": "김민수", "amount": amount,
             "members": ["김민수", "이서연"], "category": category, "memo": "", "deleted": deleted})

    def setUp(self):
        super().setUp()
        # 규격 3-4 의 예
        self._add(1, "2026-11-12", 6000, "식비")
        self._add(2, "2026-11-13", 9000, "교통")
        self._add(3, "2026-11-14", 2000, None)
        self._add(4, "2026-11-15", 4000, "식비")

    def test_spec_example(self):
        self.assertEqual(queries.category_totals(self.store, "2026-11-01", "2026-11-30"),
                         {"식비": {"count": 2, "amount": 10000},
                          "교통": {"count": 1, "amount": 9000},
                          "미분류": {"count": 1, "amount": 2000}})

    def test_period_ends_included(self):
        # 시작일(11-01)·끝일(11-30) 당일은 들어가고, 10-31·12-01 은 빠진다(규약 3)
        self._add(5, "2026-11-01", 100, "교통")
        self._add(6, "2026-11-30", 200, "교통")
        self._add(7, "2026-10-31", 1000, "교통")
        self._add(8, "2026-12-01", 1000, "교통")
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["교통"], {"count": 3, "amount": 9300})

    def test_deleted_excluded(self):
        # 삭제 표시된 지출은 건수·금액 모두에서 빠진다(규약 6-1)
        self._add(5, "2026-11-20", 50000, "식비", deleted=True)
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["식비"], {"count": 2, "amount": 10000})

    def test_blank_category_counted_as_uncategorized(self):
        # 빈 문자열·공백뿐인 분류도 "미분류" 한 칸으로 모인다(category_of 와 같은 기준)
        self._add(5, "2026-11-16", 300, "")
        self._add(6, "2026-11-17", 400, " ")
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result[UNCATEGORIZED], {"count": 3, "amount": 2700})
        self.assertNotIn(" ", result)

    def test_spaces_merged_and_old_expense_without_key(self):
        # " 식비 " 는 "식비" 칸으로, category 키가 없는 옛 지출은 "미분류" 칸으로
        self._add(5, "2026-11-16", 500, " 식비 ")
        self.store.data["expenses"].append(
            {"id": 6, "date": "2026-11-17", "payer": "김민수", "amount": 700, "members": ["김민수"]})
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["식비"], {"count": 3, "amount": 10500})
        self.assertEqual(result[UNCATEGORIZED], {"count": 2, "amount": 2700})

    def test_deleted_only_category_absent(self):
        # 삭제 지출만 있는 분류는 결과에 키가 없다(지출이 있는 분류만, 규격 3-4)
        self._add(5, "2026-11-20", 3000, "장소", deleted=True)
        self.assertNotIn("장소", queries.category_totals(self.store, "2026-11-01", "2026-11-30"))

    def test_amount_is_int_won(self):
        # 금액은 period_total 과 같은 money.to_won 으로 더해 int (2.5 → 3, "6,000" → 6000)
        self._add(5, "2026-11-21", 2.5, "교통")
        self._add(6, "2026-11-22", "6,000", "교통")
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result["교통"], {"count": 3, "amount": 15003})
        self.assertIsInstance(result["교통"]["amount"], int)

    def test_bad_category_raises(self):
        # 분류 형식이 깨진 지출이 있으면 번호를 붙인 ValueError
        self._add(5, "2026-11-23", 100, 5)
        with self.assertRaisesRegex(ValueError, "5번 지출의 분류 형식"):
            queries.category_totals(self.store, "2026-11-01", "2026-11-30")

    def test_date_object_args(self):
        # 날짜 인자는 date 객체로 줘도 같다(규격 0장)
        self.assertEqual(queries.category_totals(self.store, date(2026, 11, 1), date(2026, 11, 30)),
                         queries.category_totals(self.store, "2026-11-01", "2026-11-30"))

    def test_no_expenses_is_empty(self):
        # 기간에 지출이 없으면 빈 dict(지출이 있는 분류만 돌려준다)
        self.assertEqual(queries.category_totals(self.store, "2026-01-01", "2026-01-31"), {})

    def test_amount_sum_equals_period_total(self):
        # 분류별 금액의 합은 기간 합계(period_total)와 같다(보고서·정산·내보내기 합계 일치용)
        result = queries.category_totals(self.store, "2026-11-01", "2026-11-30")
        total = queries.period_total(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(sum(v["amount"] for v in result.values()), total)


def _expense(eid, memo, category=None, amount=9000, payer="김민수", date="2026-11-12", **kw):
    """테스트용 지출 dict. kw 로 category_fixed·deleted 를 준다(주지 않으면 키가 없는 옛 지출)."""
    e = {"id": eid, "date": date, "payer": payer, "amount": amount,
         "members": ["김민수", "이서연"], "category": category, "memo": memo}
    e.update(kw)
    return e


class RulesFileTest(StoreCase):
    """load_rules·save_rules — 규칙 파일은 JSON, 잘못된 파일은 ValueError."""

    def test_save_load_round_trip(self):
        rules = []
        categorize.add_rule(rules, "식비", ["저녁", "점심"], priority=2)
        categorize.save_rules(self.cfg["rules"], rules)
        self.assertEqual(categorize.load_rules(self.cfg["rules"]), rules)

    def test_missing_file_is_empty(self):
        self.assertEqual(categorize.load_rules(self.path("없음.json")), [])

    def test_broken_file_raises(self):
        # JSON 이 아님 / 목록이 아님 / 규칙에 분류 이름이 없음
        for text in ("{깨진", '{"category": "식비"}', '[{"keywords": ["저녁"]}]'):
            with self.subTest(text=text):
                with open(self.cfg["rules"], "w", encoding="utf-8") as f:
                    f.write(text)
                with self.assertRaises(ValueError):
                    categorize.load_rules(self.cfg["rules"])


class AddRemoveRuleTest(unittest.TestCase):
    """add_rule·remove_rule."""

    def test_add_strips_names(self):
        rules = []
        rule = categorize.add_rule(rules, " 식비 ", [" 저녁 ", ""])
        self.assertEqual((rule["category"], rule["keywords"]), ("식비", ["저녁"]))
        self.assertIs(rules[0], rule)

    def test_add_rejects_bad_rule(self):
        # 분류 이름이 비었거나, 조건이 하나도 없으면 거부
        for kwargs in ({"category": " ", "keywords": ["저녁"]}, {"category": "식비"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    categorize.add_rule([], **kwargs)

    def test_remove_out_of_range(self):
        rules = []
        categorize.add_rule(rules, "식비", ["저녁"])
        for index in (1, -1):
            with self.subTest(index=index), self.assertRaises(ValueError):
                categorize.remove_rule(rules, index)
        self.assertEqual(len(rules), 1)


class ClassifyTest(unittest.TestCase):
    """matches·classify — 키워드 하나라도, 우선순위 → 같으면 먼저 등록, 없으면 None."""

    def setUp(self):
        self.rules = []
        categorize.add_rule(self.rules, "식비", ["저녁", "점심"])
        categorize.add_rule(self.rules, "장소", ["대관", "저녁"])

    def test_any_keyword(self):
        self.assertEqual(categorize.classify(_expense(1, "토요일 점심"), self.rules), "식비")

    def test_same_priority_first_registered(self):
        # "저녁" 은 두 규칙에 다 맞음 → 우선순위 0 으로 같으니 먼저 등록한 식비
        self.assertEqual(categorize.classify(_expense(1, "저녁 대관"), self.rules), "식비")

    def test_higher_priority_wins(self):
        categorize.add_rule(self.rules, "교통", ["저녁"], priority=1)
        self.assertEqual(categorize.classify(_expense(1, "저녁"), self.rules), "교통")

    def test_no_match_is_none(self):
        for memo in ("현수막", ""):
            with self.subTest(memo=memo):
                self.assertIsNone(categorize.classify(_expense(1, memo), self.rules))


class ApplyRulesTest(StoreCase):
    """apply_rules — 고정·삭제·확정 기간은 건너뜀, preview 면 안 바꿈, [(번호, 이전, 새)]."""

    def setUp(self):
        super().setUp()
        self.rules = []
        categorize.add_rule(self.rules, "식비", ["저녁"])

    def test_old_expense_reclassified_fixed_skipped(self):
        # category_fixed 키가 없는 옛 지출은 False 로 보고 다시 분류, True 인 지출은 그대로
        self.store.data["expenses"] += [_expense(1, "저녁"), _expense(2, "저녁", "장소", category_fixed=True)]
        self.assertEqual(categorize.apply_rules(self.store, self.rules), [(1, UNCATEGORIZED, "식비")])
        self.assertEqual([e["category"] for e in self.store.data["expenses"]], ["식비", "장소"])

    def test_preview_changes_nothing(self):
        self.store.data["expenses"].append(_expense(1, "저녁"))
        self.assertEqual(categorize.apply_rules(self.store, self.rules, preview=True), [(1, UNCATEGORIZED, "식비")])
        self.assertIsNone(self.store.data["expenses"][0]["category"])
        self.assertEqual(self.store.data["history"], [])

    def test_deleted_and_locked_skipped(self):
        self.store.data["locks"].append({"start": "2026-10-01", "end": "2026-10-31"})
        self.store.data["expenses"] += [_expense(1, "저녁", deleted=True), _expense(2, "저녁", date="2026-10-31")]
        self.assertEqual(categorize.apply_rules(self.store, self.rules), [])

    def test_no_match_keeps_category_and_records_history(self):
        self.store.data["expenses"] += [_expense(1, "현수막", "장소"), _expense(2, "저녁", " 식비 "), _expense(3, "저녁", "교통")]
        self.assertEqual(categorize.apply_rules(self.store, self.rules), [(3, "교통", "식비")])
        self.assertEqual(self.store.data["expenses"][0]["category"], "장소")
        last = self.store.data["history"][-1]
        self.assertEqual((last["id"], last["action"], last["before"]["category"], last["after"]["category"]),
                         (3, "edit", "교통", "식비"))


class UncategorizedTest(StoreCase):
    """uncategorized — category_of 가 "미분류"인 지출, 삭제 표시 제외, 날짜·번호 순."""

    def test_uncategorized_list(self):
        self.store.data["expenses"] += [
            _expense(1, "", None, date="2026-11-20"), _expense(2, "", "식비"), _expense(3, "", " "),
            _expense(4, "", None, deleted=True), _expense(5, "")]
        self.assertEqual([e["id"] for e in categorize.uncategorized(self.store)], [3, 5, 1])
