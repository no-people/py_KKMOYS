"""기능 3. 월별·기간 보고서.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py expenses_in — 기간 안의 지출 목록(공용: 전원)
  - common/queries.py person_paid — 사람별 낸 돈(공용: 기능 4)
  - common/textfmt.py table, bar_chart — 글자 표와 막대그래프(공용: 기능 1·4·5의 명령)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import calendar
from datetime import date, timedelta
import os
from ..common import dates, money
from ..common.textfmt import bar_chart, pad, table, width  # noqa: F401  (보고서 기능의 표 출력은 공통 함수로 제공)
from ..common.queries import category_totals, expenses_in, period_total, person_paid

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def _to_ym_tuple(ym):
    if isinstance(ym, bool):
        raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")
    if isinstance(ym, tuple) and len(ym) == 2:
        year, month = ym
        if isinstance(year, bool) or isinstance(month, bool):
            raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")
        if not (isinstance(year, int) and isinstance(month, int)):
            raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")
        if not (1 <= month <= 12):
            raise ValueError(f"유효하지 않은 월입니다: {ym!r}")
        return (year, month)
    if isinstance(ym, str):
        parts = ym.strip().split("-")
        if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
            raise ValueError(f"유효하지 않은 연월 문자열입니다: {ym!r}")
        try:
            year = int(parts[0])
            month = int(parts[1])
        except ValueError as exc:
            raise ValueError(f"유효하지 않은 연월 문자열입니다: {ym!r}") from exc
        if not (1 <= month <= 12):
            raise ValueError(f"유효하지 않은 월입니다: {ym!r}")
        return (year, month)
    raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")


def _format_ym(ym_tuple):
    year, month = ym_tuple
    return f"{year:04d}-{month:02d}"


def _month_bounds(ym_tuple):
    year, month = ym_tuple
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def _iter_months(start_ym, end_ym):
    cur_y, cur_m = start_ym
    end_y, end_m = end_ym
    if (cur_y, cur_m) > (end_y, end_m):
        raise ValueError("start_month는 end_month보다 클 수 없습니다.")
    while (cur_y, cur_m) <= (end_y, end_m):
        yield (cur_y, cur_m)
        if cur_m == 12:
            cur_y += 1
            cur_m = 1
        else:
            cur_m += 1


def _prev_month(ym_tuple):
    year, month = ym_tuple
    if month == 1:
        return (year - 1, 12)
    return (year, month - 1)


def _expense_sort_key(expense):
    if not isinstance(expense, dict):
        return ("", 0)
    date_str = str(expense.get("date") or "")
    raw_id = expense.get("id")
    try:
        exp_id = int(raw_id) if raw_id is not None else 0
    except (TypeError, ValueError):
        exp_id = 0
    return (date_str, exp_id)


def _category_amount_map(store, start, end):
    raw = category_totals(store, start, end) or {}
    totals = {}
    for cat, val in raw.items():
        if isinstance(val, dict):
            totals[cat] = money.to_won(val.get("amount", 0))
        else:
            totals[cat] = money.to_won(val)
    return totals


def monthly_totals(store, start_month, end_month):
    """{'YYYY-MM': 합계}"""
    start_ym = _to_ym_tuple(start_month)
    end_ym = _to_ym_tuple(end_month)
    result = {}
    for ym in _iter_months(start_ym, end_ym):
        start_d, end_d = _month_bounds(ym)
        result[_format_ym(ym)] = period_total(store, start_d, end_d)
    return result


def period_summary(store, start, end):
    items = expenses_in(store, start, end)
    total = period_total(store, start, end)
    by_category = _category_amount_map(store, start, end)
    by_person = person_paid(store, start, end)
    if not items and total == 0 and not by_category and not by_person:
        return {"total": 0, "by_category": {}, "by_person": {}}
    return {
        "start": start,
        "end": end,
        "count": len(items),
        "total": total,
        "by_category": by_category,
        "by_person": by_person,
        "items": items,
    }


def month_over_month(store, month):
    """전월 대비. 돌려주는 값: (이번 달, 지난달, 증감, 증감률 % 또는 None)"""
    cur_ym = _to_ym_tuple(month)
    prev_ym = _prev_month(cur_ym)

    cur_start, cur_end = _month_bounds(cur_ym)
    prev_start, prev_end = _month_bounds(prev_ym)

    current_total = period_total(store, cur_start, cur_end)
    previous_total = period_total(store, prev_start, prev_end)
    diff = current_total - previous_total

    if previous_total == 0:
        rate = None
    else:
        rate = (diff / previous_total) * 100.0

    return (current_total, previous_total, diff, rate)


def weekday_totals(store, start, end):
    items = expenses_in(store, start, end)
    totals = {idx: 0 for idx in range(7)}
    for exp in items:
        d_str = exp.get("date")
        if not d_str:
            continue
        dt = date.fromisoformat(str(d_str)[:10])
        totals[dt.weekday()] += money.to_won(exp.get("amount", 0))
    return totals


def weekday_labels(store, start, end):
    totals = weekday_totals(store, start, end)
    return {WEEKDAYS[idx]: totals.get(idx, 0) for idx in range(7)}


def week_totals(store, start, end):
    """주(월요일 시작)별 합계. {'YYYY-MM-DD(그 주 월요일)': 합계}"""
    items = expenses_in(store, start, end)
    totals = {}
    for exp in items:
        d_str = exp.get("date")
        if not d_str:
            continue
        dt = date.fromisoformat(str(d_str)[:10])
        monday = dt - timedelta(days=dt.weekday())
        key = monday.isoformat()
        totals[key] = totals.get(key, 0) + money.to_won(exp.get("amount", 0))
    return dict(sorted(totals.items()))


def top_expenses(store, start, end, n=5, limit=None):
    items = expenses_in(store, start, end)
    count = limit if limit is not None else n
    if count <= 0:
        return []
    ranked = sorted(
        items,
        key=lambda e: (-money.to_won(e.get("amount", 0)), *_expense_sort_key(e)),
    )
    return ranked[:count]


def biggest_day(store, start, end):
    items = expenses_in(store, start, end)
    if not items:
        return None
    day_sums = {}
    for exp in items:
        d_str = str(exp.get("date") or "")[:10]
        if not d_str:
            continue
        day_sums[d_str] = day_sums.get(d_str, 0) + money.to_won(exp.get("amount", 0))
    if not day_sums:
        return None
    best_date, best_total = max(
        day_sums.items(),
        key=lambda pair: (pair[1], pair[0]),
    )
    return (best_date, best_total)


def month_report(store, month):
    ym = _to_ym_tuple(month)
    start_d, end_d = _month_bounds(ym)
    ym_label = _format_ym(ym)
    total = period_total(store, start_d, end_d)
    by_category = _category_amount_map(store, start_d, end_d)
    by_person = person_paid(store, start_d, end_d)

    lines = [
        f"[{ym_label} 월간 보고서]",
        f"총 지출: {money.fmt(total)}",
    ]

    if by_category:
        cat_rows = [[k, money.fmt(v)] for k, v in by_category.items()]
        lines.append("[분류별 지출]")
        lines.append(table(["분류", "금액"], cat_rows))
        lines.append(bar_chart(by_category))
    else:
        lines.append("[분류별 지출]")
        lines.append("내역 없음")

    if by_person:
        person_rows = [[k, money.fmt(v)] for k, v in by_person.items()]
        lines.append("[인원별 지출]")
        lines.append(table(["인원", "금액"], person_rows))
    else:
        lines.append("[인원별 지출]")
        lines.append("내역 없음")

    return "\n".join(lines) + "\n"


def save_report(text, path):
    """보고서를 텍스트 파일(.txt)로 저장한다."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def search(store, start=None, end=None, person=None, min_amount=None, max_amount=None, word=None):
    """지출 검색. 기간, 사람(낸 사람이거나 참여자), 금액 범위, 메모 낱말로 찾는다. 삭제된 지출은 빼고 날짜순."""
    if start is not None or end is not None:
        if start is None or end is None:
            raise ValueError("기간 검색에는 start와 end를 함께 지정해야 합니다.")
        candidates = expenses_in(store, start, end, include_deleted=False)
    else:
        data = getattr(store, "data", None)
        raw_expenses = data.get("expenses", []) if isinstance(data, dict) else []
        candidates = [
            e for e in raw_expenses
            if isinstance(e, dict) and not e.get("deleted")
        ]

    min_won = money.to_won(min_amount) if min_amount is not None else None
    max_won = money.to_won(max_amount) if max_amount is not None else None
    if min_won is not None and max_won is not None and min_won > max_won:
        raise ValueError("min_amount는 max_amount보다 클 수 없습니다.")

    query_word = word.strip().lower() if isinstance(word, str) else None

    matched = []
    for exp in candidates:
        if not isinstance(exp, dict) or exp.get("deleted"):
            continue

        amount = money.to_won(exp.get("amount", 0))
        if min_won is not None and amount < min_won:
            continue
        if max_won is not None and amount > max_won:
            continue

        if person is not None:
            members = exp.get("members")
            member_list = members if isinstance(members, (list, tuple, set)) else []
            if exp.get("payer") != person and person not in member_list:
                continue

        if query_word:
            memo = str(exp.get("memo") or "").lower()
            if query_word not in memo:
                continue

        matched.append(exp)

    matched.sort(key=_expense_sort_key)
    return matched