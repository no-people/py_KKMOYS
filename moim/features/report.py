from datetime import date, timedelta
import os

from moim.common import dates, money, queries, textfmt


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

def _to_ym_tuple(ym):
    if isinstance(ym, tuple) and len(ym) == 2:
        year, month = int(ym[0]), int(ym[1])
        if not (1 <= month <= 12):
            raise ValueError(f"달 형식이 잘못되었습니다(YYYY-MM): {ym}")
        return (year, month)
    if isinstance(ym, str) and hasattr(dates, "parse_month"):
        parsed = dates.parse_month(ym)
        if isinstance(parsed, tuple) and len(parsed) == 2:
            return parsed
        if hasattr(parsed, "year") and hasattr(parsed, "month"):
            return (parsed.year, parsed.month)
    raise ValueError(f"달 형식이 잘못되었습니다(YYYY-MM): {ym}")

def save_report(store, ym, out_path):
    """월간 보고서를 UTF-8 텍스트 파일로 저장하고 경로를 돌려준다."""
    content = month_report(store, ym)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def search(store, start=None, end=None, payer=None, min_amount=None, max_amount=None, keyword=None):
    """기간·사람·금액 범위·낱말로 삭제되지 않은 지출을 검색한다."""
    if start is not None or end is not None:
        s = start if start is not None else "0001-01-01"
        e = end if end is not None else "9999-12-31"
        candidates = queries.expenses_in(store, s, e, include_deleted=False)
    else:
        candidates = [
            exp for exp in store.data.get("expenses", [])
            if not exp.get("deleted")
        ]

    min_won = money.to_won(min_amount) if min_amount is not None else None
    max_won = money.to_won(max_amount) if max_amount is not None else None
    kw = keyword.strip().lower() if keyword else None

    matched = []
    for exp in candidates:
        amt = money.to_won(exp["amount"])
        if payer is not None and exp.get("payer") != payer:
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