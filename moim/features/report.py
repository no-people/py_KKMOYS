"""기능 3. 월별·기간 보고서.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py expenses_in — 기간 안의 지출 목록(공용: 전원)
  - common/queries.py person_paid — 사람별 낸 돈(공용: 기능 4)
  - common/textfmt.py table, bar_chart — 글자 표와 막대그래프(공용: 기능 1·4·5의 명령)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""
import os
from ..common import dates, money
from ..common.textfmt import bar_chart, pad, table, width  # noqa: F401  (보고서 기능의 표 출력은 공통 함수로 제공)
from ..common.queries import category_totals, expenses_in, period_total, person_paid

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

def monthly_totals(store, start_ym, end_ym):
    """월별 지출 합계 dict {"YYYY-MM": total_int} 을 돌려준다."""
    s_ym = _to_ym_tuple(start_ym)
    e_ym = _to_ym_tuple(end_ym)
    result = {}
    for ym in dates.months_between(s_ym, e_ym):
        start_d, end_d = dates.month_range(ym[0], ym[1])
        key = f"{ym[0]:04d}-{ym[1]:02d}"
        result[key] = queries.period_total(store, start_d, end_d)
    return result


def period_summary(store, start, end):
    """기간 요약: total, by_category, by_person."""
    raw_cats = queries.category_totals(store, start, end)
    by_category = {cat: info["amount"] for cat, info in raw_cats.items()}
    return {
        "total": queries.period_total(store, start, end),
        "by_category": by_category,
        "by_person": queries.person_paid(store, start, end),
    }


def month_over_month(store, ym):
    """전월 대비 지출 증감 정보."""
    year, month = year, month = _to_ym_tuple(ym) if hasattr(dates, "parse_month") else ym
    cur_start, cur_end = dates.month_range(year, month)
    cur_total = queries.period_total(store, cur_start, cur_end)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    prev_start, prev_end = dates.month_range(prev_year, prev_month)
    prev_total = queries.period_total(store, prev_start, prev_end)

    diff = cur_total - prev_total
    return {
        "month": f"{year:04d}-{month:02d}",
        "prev_month": f"{prev_year:04d}-{prev_month:02d}",
        "total": cur_total,
        "prev_total": prev_total,
        "diff": diff,
    }


def weekday_totals(store, start, end):
    """요일별(0=월 ~ 6=일) 지출 합계 dict."""
    totals = {i: 0 for i in range(7)}
    for exp in queries.expenses_in(store, start, end, include_deleted=False):
        d = dates.parse(exp["date"])
        totals[d.weekday()] += money.to_won(exp["amount"])
    return totals


def week_totals(store, start, end):
    """월요일 시작 주별 지출 합계 dict {주_시작일_문자열: 합계}."""
    totals = {}
    for exp in queries.expenses_in(store, start, end, include_deleted=False):
        d = dates.parse(exp["date"])
        week_start = d - timedelta(days=d.weekday())
        key = dates.fmt(week_start)
        totals[key] = totals.get(key, 0) + money.to_won(exp["amount"])
    return totals


def top_expenses(store, start, end, limit=5):
    """기간 내 지출 중 금액이 큰 순으로 상위 limit건."""
    items = queries.expenses_in(store, start, end, include_deleted=False)
    ranked = sorted(
        items,
        key=lambda e: (-money.to_won(e["amount"]), e.get("date", ""), e.get("id", 0)),
    )
    return ranked[:limit]


def biggest_day(store, start, end):
    """기간 내 하루 지출 합계가 가장 큰 (날짜_문자열, 합계) 또는 None."""
    by_day = {}
    for exp in queries.expenses_in(store, start, end, include_deleted=False):
        key = dates.fmt(dates.parse(exp["date"]))
        by_day[key] = by_day.get(key, 0) + money.to_won(exp["amount"])
    if not by_day:
        return None
    best_day = max(by_day.items(), key=lambda kv: (kv[1], kv[0]))
    return best_day


def month_report(store, ym):
    """월간 보고서 문자열 생성."""
    year, month = _to_ym_tuple(ym)
    start_d, end_d = dates.month_range(year, month)
    total = queries.period_total(store, start_d, end_d)
    by_category_detail = queries.category_totals(store, start_d, end_d)
    by_person = queries.person_paid(store, start_d, end_d)

    cat_rows = [
        [cat, info["count"], info["amount"]]
        for cat, info in by_category_detail.items()
    ]
    cat_table = textfmt.table(
        ["분류", "건수", "금액"],
        cat_rows,
        total=["합계", sum(info["count"] for info in by_category_detail.values()), total],
        numeric={1, 2},
    )

    person_rows = [[name, amt] for name, amt in by_person.items()]
    person_table = textfmt.table(
        ["이름", "낸 돈"],
        person_rows,
        total=["합계", sum(by_person.values())],
        numeric={1},
    )

    chart = textfmt.bar_chart(
        {cat: info["amount"] for cat, info in by_category_detail.items()},
        bar_width=20,
    )

    return "\n\n".join([
        f"[{year:04d}-{month:02d} 월간 보고서] 총 지출: {money.fmt(total)}원",
        cat_table,
        chart,
        person_table,
    ])


def _to_ym_tuple(month):
    if isinstance(month, tuple) and len(month) == 2:
        year, mon = int(month[0]), int(month[1])
        if not (1 <= mon <= 12):
            raise ValueError(f"달 형식이 잘못되었습니다(YYYY-MM): {month}")
        return (year, mon)
    if isinstance(month, str) and hasattr(dates, "parse_month"):
        parsed = dates.parse_month(month)
        if isinstance(parsed, tuple) and len(parsed) == 2:
            return parsed
        if hasattr(parsed, "year") and hasattr(parsed, "month"):
            return (parsed.year, parsed.month)
    raise ValueError(f"달 형식이 잘못되었습니다(YYYY-MM): {month}")


def monthly_totals(store, start_month, end_month):
    """{'YYYY-MM': 합계}"""
    s_ym = _to_ym_tuple(start_month)
    e_ym = _to_ym_tuple(end_month)
    result = {}
    for ym in dates.months_between(s_ym, e_ym):
        start_d, end_d = dates.month_range(ym[0], ym[1])
        key = f"{ym[0]:04d}-{ym[1]:02d}"
        result[key] = period_total(store, start_d, end_d)
    return result


def period_summary(store, start, end):
    raw_cats = category_totals(store, start, end)
    by_category = {cat: info["amount"] for cat, info in raw_cats.items()}
    return {
        "total": period_total(store, start, end),
        "by_category": by_category,
        "by_person": person_paid(store, start, end),
    }


def month_over_month(store, month):
    """전월 대비. 돌려주는 값: (이번 달, 지난달, 증감, 증감률 % 또는 None)"""
    year, mon = _to_ym_tuple(month)
    cur_start, cur_end = dates.month_range(year, mon)
    cur_total = period_total(store, cur_start, cur_end)

    prev_year, prev_mon = (year - 1, 12) if mon == 1 else (year, mon - 1)
    prev_start, prev_end = dates.month_range(prev_year, prev_mon)
    prev_total = period_total(store, prev_start, prev_end)

    diff = cur_total - prev_total
    rate = None if prev_total == 0 else round((diff / prev_total) * 100, 1)
    return (cur_total, prev_total, diff, rate)


def weekday_totals(store, start, end):
    raise NotImplementedError("이 함수를 구현한다")


def week_totals(store, start, end):
    """주(월요일 시작)별 합계. {'YYYY-MM-DD(그 주 월요일)': 합계}"""
    raise NotImplementedError("이 함수를 구현한다")


def top_expenses(store, start, end, n=5):
    raise NotImplementedError("이 함수를 구현한다")


def biggest_day(store, start, end):
    raise NotImplementedError("이 함수를 구현한다")


def month_report(store, month):
    year, mon = _to_ym_tuple(month)
    start_d, end_d = dates.month_range(year, mon)
    total = period_total(store, start_d, end_d)
    by_category_detail = category_totals(store, start_d, end_d)
    by_person = person_paid(store, start_d, end_d)

    cat_rows = [[cat, info["count"], info["amount"]] for cat, info in by_category_detail.items()]
    cat_table = table(
        ["분류", "건수", "금액"],
        cat_rows,
        total=["합계", sum(info["count"] for info in by_category_detail.values()), total],
        numeric={1, 2},
    )
    person_table = table(
        ["이름", "낸 돈"],
        [[name, amt] for name, amt in by_person.items()],
        total=["합계", sum(by_person.values())],
        numeric={1},
    )
    chart = bar_chart({cat: info["amount"] for cat, info in by_category_detail.items()}, bar_width=20)

    return "\n\n".join([
        f"[{year:04d}-{mon:02d} 월간 보고서] 총 지출: {money.fmt(total)}원",
        cat_table,
        chart,
        person_table,
    ])


def save_report(text, path):
    """보고서를 텍스트 파일(.txt)로 저장한다."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def search(store, start=None, end=None, person=None, min_amount=None, max_amount=None, word=None):
    """지출 검색. 기간, 사람(낸 사람이거나 참여자), 금액 범위, 메모 낱말로 찾는다. 삭제된 지출은 빼고 날짜순."""
    raise NotImplementedError("이 함수를 구현한다")
    min_won = money.to_won(min_amount) if min_amount is not None else None
    max_won = money.to_won(max_amount) if max_amount is not None else None
    kw = word.strip().lower() if word else None

    matched = []
    for exp in candidates:
        amt = money.to_won(exp["amount"])
        if person is not None:
            is_payer = exp.get("payer") == person
            is_member = person in exp.get("members", [])
            if not (is_payer or is_member):
                continue
        if min_won is not None and amt < min_won:
            continue
        if max_won is not None and amt > max_won:
            continue
        if kw:
            haystack = f"{exp.get('memo', '')} {exp.get('category') or ''}".lower()
            if kw not in haystack:
                continue
        matched.append(exp)
    return matched