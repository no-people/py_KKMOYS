"""기능 3. 월별·기간 보고서.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py expenses_in — 기간 안의 지출 목록(공용: 전원)
  - common/queries.py person_paid — 사람별 낸 돈(공용: 기능 4)
  - common/textfmt.py table, bar_chart — 글자 표와 막대그래프(공용: 기능 1·4·5의 명령)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import calendar
import os
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from ..common import dates, money
from ..common.textfmt import bar_chart, pad, table, width  # noqa: F401  (보고서 기능의 표 출력은 공통 함수로 제공)
from ..common.queries import category_totals, expenses_in, period_total, person_paid
from ..common.rules import UNCATEGORIZED

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
BAR_WIDTH = 30


def _to_ym_tuple(ym):
    if isinstance(ym, bool):
        raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")
    if isinstance(ym, tuple) and len(ym) == 2:
        year, month = ym
        if isinstance(year, bool) or isinstance(month, bool):
            raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")
        if not (isinstance(year, int) and isinstance(month, int)):
            raise ValueError(f"유효하지 않은 연월입니다: {ym!r}")
        if year < 1:
            raise ValueError("연도는 1 이상이어야 합니다.")
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
        if year < 1:
            raise ValueError("연도는 1 이상이어야 합니다.")
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
    total = period_total(store, start, end)
    by_category = _category_amount_map(store, start, end)
    by_person = person_paid(store, start, end)
    return {
        "total": total,
        "by_category": by_category,
        "by_person": by_person,
    }


def month_over_month(store, month):
    """전월 대비. 돌려주는 값: (이번 달, 지난달, 증감, 증감률 % 또는 None)"""
    year, mon = _to_ym_tuple(month)
    prev_ym = (year - 1, 12) if mon == 1 else (year, mon - 1)

    cur_total = period_total(store, *_month_bounds((year, mon)))
    prev_total = period_total(store, *_month_bounds(prev_ym))
    diff = cur_total - prev_total

    if prev_total == 0:
        rate = None
    else:
        raw_rate = (Decimal(diff) * Decimal(100)) / Decimal(prev_total)
        rate = float(raw_rate.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) or 0.0

    return (cur_total, prev_total, diff, rate)


def weekday_totals(store, start, end):
    """요일별 지출 합계. {'월': 합계, ..., '일': 합계} (지출이 없는 요일도 0원으로 포함)."""
    start_d = dates.parse(start)
    end_d = dates.parse(end)
    if start_d > end_d:
        raise ValueError("시작일이 끝일보다 늦을 수 없습니다.")

    items = expenses_in(store, start_d, end_d)
    totals = {day: 0 for day in WEEKDAYS}
    for e in items:
        d = dates.parse(e["date"])
        totals[WEEKDAYS[d.weekday()]] += money.to_won(e["amount"])
    return totals


def week_totals(store, start, end):
    """주(월요일 시작)별 합계. {'YYYY-MM-DD(그 주 월요일)': 합계}

    첫 주의 시작일 키는 지정 기간 이전의 월요일이 될 수 있으나,
    합계에는 지정한 [start, end] 기간 안의 지출만 포함된다.
    """
    start_d = dates.parse(start)
    end_d = dates.parse(end)
    if start_d > end_d:
        raise ValueError("시작일이 끝일보다 늦을 수 없습니다.")

    items = expenses_in(store, start_d, end_d)
    first_monday = start_d - timedelta(days=start_d.weekday())
    last_monday = end_d - timedelta(days=end_d.weekday())

    totals = {}
    cur = first_monday
    while cur <= last_monday:
        totals[cur.isoformat()] = 0
        cur += timedelta(days=7)

    for e in items:
        d = dates.parse(e["date"])
        monday = d - timedelta(days=d.weekday())
        totals[monday.isoformat()] += money.to_won(e["amount"])
    return totals


def weekday_table(store, start, end):
    """요일별 지출 합계 표와 막대그래프."""
    totals = weekday_totals(store, start, end)
    rows = [[day, totals[day]] for day in WEEKDAYS]
    body = table(["요일", "지출 합계"], rows, total=["합계", sum(totals.values())], numeric={1})
    chart = bar_chart(totals, bar_width=BAR_WIDTH)
    return f"{body}\n\n{chart}"


def week_table(store, start, end):
    """주(월요일 시작)별 지출 합계 표와 막대그래프."""
    totals = week_totals(store, start, end)
    rows = [[week_start, amt] for week_start, amt in totals.items()]
    body = table(["주 시작일(월)", "지출 합계"], rows, total=["합계", sum(totals.values())], numeric={1})
    chart = bar_chart(totals, bar_width=BAR_WIDTH)
    return f"{body}\n\n{chart}"


def top_expenses(store, start, end, n=5):
    raise NotImplementedError("이 함수를 구현한다")


def biggest_day(store, start, end):
    raise NotImplementedError("이 함수를 구현한다")


def category_table(store, start, end):
    """기간의 분류별 건수·금액 표와 금액 막대그래프. 금액 큰 순, 미분류는 맨 뒤."""
    totals = category_totals(store, start, end) or {}
    if not totals:
        return "내역 없음"
    order = sorted(totals, key=lambda c: (c == UNCATEGORIZED, -money.to_won(totals[c]["amount"]), c))
    rows = [[c, totals[c]["count"], money.to_won(totals[c]["amount"])] for c in order]
    count_sum = sum(r[1] for r in rows)
    amount_sum = sum(r[2] for r in rows)
    if amount_sum != period_total(store, start, end):   # 분류 합계 = 기간 합계 (합계 불일치 방지)
        raise ValueError("분류별 합계가 기간 합계와 다릅니다")
    body = table(["분류", "건수", "금액"], rows, total=["합계", count_sum, amount_sum], numeric={1, 2})
    chart = bar_chart({r[0]: r[2] for r in rows}, bar_width=BAR_WIDTH)
    return f"{body}\n\n{chart}"


def monthly_table(store, start_month, end_month):
    """달별 지출 합계 표와 막대그래프. 지출이 없는 달은 0원으로 나온다."""
    amounts = monthly_totals(store, start_month, end_month)   # {'YYYY-MM': 합계}
    rows = [[k, v] for k, v in amounts.items()]
    body = table(["월", "지출 합계"], rows, total=["합계", sum(amounts.values())], numeric={1})
    chart = bar_chart(amounts, bar_width=BAR_WIDTH)
    return f"{body}\n\n{chart}"


def monthly_trend_table(store, start_month, end_month):
    """여러 달 지출 추이 표(월별 합계·전월 대비 증감·증감률)와 막대그래프."""
    amounts = monthly_totals(store, start_month, end_month)
    rows = []
    prev_amt = None
    for ym_str, amt in amounts.items():
        if prev_amt is None:
            diff_str = "-"
            rate_str = "-"
        else:
            diff = amt - prev_amt
            sign = "+" if diff > 0 else ""
            diff_str = f"{sign}{money.fmt(diff)}"
            if prev_amt == 0:
                rate_str = "-"
            else:
                raw_rate = (Decimal(diff) * Decimal(100)) / Decimal(prev_amt)
                rate = float(raw_rate.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)) or 0.0
                rate_str = f"{sign}{rate:.1f}%"
        rows.append([ym_str, amt, diff_str, rate_str])
        prev_amt = amt

    body = table(
        ["월", "지출 합계", "전월 대비", "증감률"],
        rows,
        total=["합계", sum(amounts.values()), "", ""],
        numeric={1, 2, 3},
    )
    chart = bar_chart(amounts, bar_width=BAR_WIDTH)
    return f"{body}\n\n{chart}"


def month_report(store, month):
    """월간 보고서: 총 지출, 분류별 표·그래프, 인원별 낸 돈 표."""
    ym = _to_ym_tuple(month)
    start_d, end_d = _month_bounds(ym)
    total = period_total(store, start_d, end_d)
    by_person = person_paid(store, start_d, end_d)

    lines = [f"[{_format_ym(ym)} 월간 보고서]", f"총 지출: {money.fmt(total)}", "", "[분류별 지출]",
             category_table(store, start_d, end_d), "", "[인원별 지출]"]
    if by_person:
        rows = [[k, v] for k, v in by_person.items()]
        lines.append(table(["인원", "낸 돈"], rows, total=["합계", sum(by_person.values())], numeric={1}))
    else:
        lines.append("내역 없음")
    return "\n".join(lines) + "\n"


def save_report(text, path):
    """보고서를 텍스트 파일(.txt)로 저장한다."""
    raise NotImplementedError("이 함수를 구현한다")


def _normalize_amount(raw, label):
    if raw is None:
        return None
    if isinstance(raw, str):
        cleaned = raw.strip()
        if cleaned == "":
            return None
        raw = cleaned
    try:
        return money.to_won(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 금액 형식이 올바르지 않습니다: {raw!r}") from exc


def search(store, start=None, end=None, person=None, min_amount=None, max_amount=None, word=None):
    """지출 검색. 기간, 사람(낸 사람이거나 참여자), 금액 범위, 메모 낱말로 찾는다. 삭제된 지출은 빼고 날짜순."""
    if person is not None and not isinstance(person, str):
        raise ValueError(f"사람 이름은 문자열이어야 합니다: {person!r}")
    if word is not None and not isinstance(word, str):
        raise ValueError(f"낱말은 문자열이어야 합니다: {word!r}")

    eff_start = start.strip() or None if isinstance(start, str) else start
    eff_end = end.strip() or None if isinstance(end, str) else end

    if eff_start is not None and eff_end is not None:
        if dates.parse(eff_start) > dates.parse(eff_end):
            raise ValueError("시작일이 끝일보다 늦을 수 없습니다.")
    elif eff_start is not None:
        dates.parse(eff_start)
    elif eff_end is not None:
        dates.parse(eff_end)

    min_won = _normalize_amount(min_amount, "최소")
    max_won = _normalize_amount(max_amount, "최대")
    if min_won is not None and max_won is not None and min_won > max_won:
        raise ValueError("최소 금액이 최대 금액보다 클 수 없습니다.")

    keyword = word.strip() if word is not None else None
    if keyword == "":
        keyword = None

    person_filter = person.strip() if person is not None and person.strip() else None

    query_start = eff_start if eff_start is not None else "0001-01-01"
    query_end = eff_end if eff_end is not None else "9999-12-31"
    candidates = expenses_in(store, query_start, query_end)

    results = []
    for e in candidates:
        if e.get("deleted"):
            continue

        if person_filter is not None:
            members = e.get("members") or []
            if e.get("payer") != person_filter and person_filter not in members:
                continue

        amt = money.to_won(e.get("amount", 0))
        if min_won is not None and amt < min_won:
            continue
        if max_won is not None and amt > max_won:
            continue

        if keyword is not None:
            memo = e.get("memo") or ""
            if keyword not in memo:
                continue

        results.append(e)

    return results
