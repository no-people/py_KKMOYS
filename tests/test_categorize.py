"""기능 2 분류 규칙 테스트. 자료 항목 category_fixed 포함."""

import contextlib
import io
import json
import unittest
from datetime import date

from helpers import StoreCase

from moim import cli
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

    def test_reapply_after_rules_changed(self):
        # 규칙을 바꾼 뒤 다시 분류하면 이미 분류된 지출도 새 규칙을 따르고, 고정된 지출은 그대로(확장 필수)
        self.store.data["expenses"] += [_expense(1, "저녁"), _expense(2, "회의 후 저녁"),
                                        _expense(3, "저녁", "장소", category_fixed=True)]
        categorize.apply_rules(self.store, self.rules)
        categorize.add_rule(self.rules, "회식", ["저녁"], priority=1)
        self.assertEqual(categorize.apply_rules(self.store, self.rules), [(1, "식비", "회식"), (2, "식비", "회식")])
        self.assertEqual([e["category"] for e in self.store.data["expenses"]], ["회식", "회식", "장소"])

    def test_error_midway_changes_nothing(self):
        # 뒤쪽 지출의 금액·분류 형식이 잘못되면 ValueError, 앞쪽 지출도 바뀌지 않고 이력도 없다(#68 의견 3)
        for bad in (_expense(2, "저녁", amount="abc"), _expense(2, "저녁", 5)):
            with self.subTest(bad=bad):
                self.store.data["expenses"] = [_expense(1, "저녁"), bad]
                with self.assertRaises(ValueError):
                    categorize.apply_rules(self.store, self.rules)
                self.assertIsNone(self.store.data["expenses"][0]["category"])
                self.assertEqual(self.store.data["history"], [])

    def test_broken_history_changes_nothing(self):
        # 이력 칸이 깨져 있으면 ValueError, 지출은 바뀌지 않는다
        self.store.data["expenses"].append(_expense(1, "저녁"))
        self.store.data["history"] = "깨짐"
        with self.assertRaises(ValueError):
            categorize.apply_rules(self.store, self.rules)
        self.assertIsNone(self.store.data["expenses"][0]["category"])


class SetCategoryTest(StoreCase):
    """set_category·unfix_category — 직접 지정하면 고정, 다시 분류해도 그대로. 고정을 풀면 규칙을 따름."""

    def setUp(self):
        super().setUp()
        self.rules = []
        categorize.add_rule(self.rules, "식비", ["저녁"])
        self.store.data["expenses"].append(_expense(1, "회의 후 저녁"))

    def test_set_fixes_and_apply_keeps(self):
        # 앞뒤 공백은 떼고 고정, 그 뒤 다시 분류해도 바뀌지 않는다
        e = categorize.set_category(self.store, 1, " 장소 ")
        self.assertEqual((e["category"], e["category_fixed"]), ("장소", True))
        self.assertEqual(categorize.apply_rules(self.store, self.rules), [])
        self.assertEqual(self.store.data["expenses"][0]["category"], "장소")

    def test_unfix_then_apply_follows_rule(self):
        categorize.set_category(self.store, 1, "장소")
        e = categorize.unfix_category(self.store, 1)
        self.assertEqual((e["category"], e["category_fixed"]), ("장소", False))   # 분류 이름은 그대로
        self.assertEqual(categorize.apply_rules(self.store, self.rules), [(1, "장소", "식비")])

    def test_history_recorded(self):
        categorize.set_category(self.store, 1, "장소")
        categorize.unfix_category(self.store, 1)
        got = [(h["id"], h["action"], h["before"].get("category_fixed"), h["after"]["category_fixed"])
               for h in self.store.data["history"]]
        self.assertEqual(got, [(1, "edit", None, True), (1, "edit", True, False)])

    def test_bad_input_raises_and_changes_nothing(self):
        self.store.data["locks"].append({"start": "2026-10-01", "end": "2026-10-31"})
        self.store.data["expenses"] += [_expense(2, "", deleted=True), _expense(3, "", date="2026-10-31")]
        for eid, category in [(1, ""), (1, "  "), (1, None), (9, "장소"), (2, "장소"), (3, "장소")]:
            with self.subTest(eid=eid, category=category):
                with self.assertRaises(ValueError):
                    categorize.set_category(self.store, eid, category)
        self.assertEqual([e.get("category_fixed") for e in self.store.data["expenses"]], [None, None, None])
        self.assertEqual(self.store.data["history"], [])

    def test_unfix_not_fixed_raises(self):
        # 고정되지 않은 지출(키가 없는 옛 지출 포함)은 풀 것이 없다
        with self.assertRaises(ValueError):
            categorize.unfix_category(self.store, 1)

    def test_unfix_bad_input_raises_and_changes_nothing(self):
        # 없는 번호·삭제 표시·확정 기간은 unfix_category 도 거부(set_category 와 같은 검사)
        self.store.data["locks"].append({"start": "2026-10-01", "end": "2026-10-31"})
        self.store.data["expenses"] += [_expense(2, "", "장소", deleted=True, category_fixed=True),
                                        _expense(3, "", "장소", date="2026-10-31", category_fixed=True)]
        for eid in (9, 2, 3):
            with self.subTest(eid=eid):
                with self.assertRaises(ValueError):
                    categorize.unfix_category(self.store, eid)
        self.assertEqual([e["category_fixed"] for e in self.store.data["expenses"][1:]], [True, True])
        self.assertEqual(self.store.data["history"], [])


class UncategorizedTest(StoreCase):
    """uncategorized — category_of 가 "미분류"인 지출, 삭제 표시 제외, 날짜·번호 순."""

    def test_uncategorized_list(self):
        self.store.data["expenses"] += [
            _expense(1, "", None, date="2026-11-20"), _expense(2, "", "식비"), _expense(3, "", " "),
            _expense(4, "", None, deleted=True), _expense(5, "")]
        self.assertEqual([e["id"] for e in categorize.uncategorized(self.store)], [3, 5, 1])


class CatCommandTest(StoreCase):
    """명령 cat — add·remove·list·apply·uncat·set·unfix. cli.main([...]) 으로 실행한다."""

    def setUp(self):
        super().setUp()
        self.config = self.path("config.json")
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path, "rules": self.cfg["rules"]}, f, ensure_ascii=False)
        self.store.data["expenses"] += [_expense(1, "회의 후 저녁"), _expense(2, "현수막", amount=36000),
                                        _expense(3, "저녁", "장소", category_fixed=True)]
        self.store.save()

    def cat(self, *argv):
        lines = []
        cli.main(["--config", self.config, "cat", *argv], out=lines.append)
        return lines

    def saved(self):
        return Store(self.store.path).load().data["expenses"]

    def test_add_list_remove(self):
        self.assertEqual(self.cat("add", "식비", "--keywords", "저녁", "점심"),
                         ["규칙 추가: 0. 식비  키워드: 저녁, 점심  우선순위: 0"])
        self.cat("add", "장소", "--keywords", "대관", "--priority", "1", "--min", "10,000")
        self.assertEqual(self.cat("list"), ["0. 식비  키워드: 저녁, 점심  우선순위: 0",
                                            "1. 장소  키워드: 대관  금액: 10,000원~  우선순위: 1"])
        self.assertEqual(self.cat("remove", "0"), ["규칙 삭제: 0. 식비"])
        self.assertEqual([r["category"] for r in categorize.load_rules(self.cfg["rules"])], ["장소"])

    def test_list_empty(self):
        self.assertEqual(self.cat("list"), ["등록된 규칙이 없습니다"])

    def test_bad_input_error_message(self):
        # 조건 없는 규칙·없는 번호는 "오류: 이유" 한 줄과 종료 코드 1(#56 통합 실행 오류 안내)
        for argv, reason in ((("add", "식비"), "키워드·낸 사람·금액 범위 가운데 조건을 하나 이상 주세요"),
                             (("remove", "0"), "0번 규칙이 없습니다")):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = cli.main(["--config", self.config, "cat", *argv], out=print)
                self.assertEqual((code, err.getvalue()), (1, f"오류: {reason}\n"))

    def test_apply_preview_then_apply(self):
        self.cat("add", "식비", "--keywords", "저녁")
        self.assertEqual(self.cat("apply", "--preview"),
                         ["1번: 미분류 → 식비", "(미리 보기) 1건이 바뀝니다. 자료는 바꾸지 않았습니다"])
        self.assertIsNone(self.saved()[0]["category"])
        self.assertEqual(self.cat("apply"), ["1번: 미분류 → 식비", "1건을 다시 분류했습니다"])
        # 저장됨, 고정된 3번은 그대로
        self.assertEqual([e["category"] for e in self.saved()], ["식비", None, "장소"])

    def test_uncat(self):
        self.assertEqual(self.cat("uncat"), ["1번  2026-11-12  9,000원  김민수  회의 후 저녁",
                                             "2번  2026-11-12  36,000원  김민수  현수막", "미분류 2건"])

    def test_set_then_apply_keeps_fixed(self):
        # 직접 지정은 앞뒤 공백을 떼고 고정한 뒤 저장, 다시 분류해도 그대로(확장 필수 "직접 지정 + 고정")
        self.assertEqual(self.cat("set", "2", " 물품 "), ["분류 지정 2번: 물품 (고정, cat unfix 2 로 풀기)"])
        e = self.saved()[1]
        self.assertEqual((e["category"], e["category_fixed"]), ("물품", True))
        self.cat("add", "식비", "--keywords", "저녁", "현수막")
        self.assertEqual(self.cat("apply"), ["1번: 미분류 → 식비", "1건을 다시 분류했습니다"])
        self.assertEqual([e["category"] for e in self.saved()], ["식비", "물품", "장소"])

    def test_unfix_then_apply_follows_rule(self):
        # 고정을 풀면 분류 이름은 그대로 저장되고, 다음 다시 분류 때 규칙을 따른다
        self.assertEqual(self.cat("unfix", "3"), ["분류 고정 풀기 3번: 장소 (다음 cat apply 때 규칙을 따름)"])
        e = self.saved()[2]
        self.assertEqual((e["category"], e["category_fixed"]), ("장소", False))
        self.cat("add", "식비", "--keywords", "저녁")
        self.assertEqual(self.cat("apply"), ["1번: 미분류 → 식비", "3번: 장소 → 식비", "2건을 다시 분류했습니다"])

    def test_set_without_rules_setting(self):
        # set·unfix 는 규칙 파일을 쓰지 않으므로 설정에 rules 가 없어도 된다
        with open(self.config, "w", encoding="utf-8") as f:
            json.dump({"data": self.store.path}, f, ensure_ascii=False)
        self.assertEqual(self.cat("set", "1", "식비"), ["분류 지정 1번: 식비 (고정, cat unfix 1 로 풀기)"])
        self.assertEqual(self.cat("unfix", "1"), ["분류 고정 풀기 1번: 식비 (다음 cat apply 때 규칙을 따름)"])

    def test_set_unfix_bad_input_error_message(self):
        # 없는 번호·빈 분류·고정 안 된 지출은 "오류: 이유" 한 줄과 종료 코드 1, 자료는 그대로
        for argv, reason in ((("set", "9", "식비"), "9번 지출이 없습니다"),
                             (("set", "1", " "), "분류 이름을 입력하세요"),
                             (("unfix", "1"), "고정되지 않은 지출입니다: 1번")):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = cli.main(["--config", self.config, "cat", *argv], out=print)
                self.assertEqual((code, err.getvalue()), (1, f"오류: {reason}\n"))
        self.assertEqual([(e["category"], e.get("category_fixed")) for e in self.saved()],
                         [(None, None), (None, None), ("장소", True)])


class SummaryTest(StoreCase):
    """summary — 분류별 건수·금액. 공통 모듈 category_totals 결과를 그대로 쓴다."""

    def setUp(self):
        super().setUp()
        self.store.data["expenses"] += [
            _expense(1, "", "식비", 6000, date="2026-11-01"),     # 시작일 당일
            _expense(2, "", " 식비 ", 4000, date="2026-11-30"),   # 끝일 당일, 앞뒤 공백은 "식비"
            _expense(3, "", "교통", 9000, date="2026-11-13", category_fixed=True),
            _expense(4, "", None, 2000, date="2026-11-14"),
            _expense(5, "", "식비", 50000, date="2026-11-15", deleted=True),
            _expense(6, "", "식비", 1000, date="2026-10-31"),     # 기간 밖
            _expense(7, "", "교통", 1000, date="2026-12-01")]     # 기간 밖

    def test_counts_and_amounts(self):
        self.assertEqual(categorize.summary(self.store, "2026-11-01", "2026-11-30"),
                         {"식비": {"count": 2, "amount": 10000},
                          "교통": {"count": 1, "amount": 9000},
                          UNCATEGORIZED: {"count": 1, "amount": 2000}})

    def test_same_as_common_function_and_period_total(self):
        # 보고서·예산과 같은 공통 함수 결과이고, 금액 합은 기간 합계와 같다
        result = categorize.summary(self.store, "2026-11-01", "2026-11-30")
        self.assertEqual(result, queries.category_totals(self.store, "2026-11-01", "2026-11-30"))
        self.assertEqual(sum(v["amount"] for v in result.values()),
                         queries.period_total(self.store, "2026-11-01", "2026-11-30"))

    def test_no_expenses_is_empty(self):
        self.assertEqual(categorize.summary(self.store, "2026-01-01", "2026-01-31"), {})

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            categorize.summary(self.store, "2026-13-01", "2026-11-30")
