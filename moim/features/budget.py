"""기능 5. 예산·회비.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py is_member_active — 그날 회원인가(공용: 기능 1의 지출 검사)
  - common/queries.py active_members — 그날 회원 목록
  - common/dates.py months_between — 두 달 사이의 달 목록(공용: 기능 3)
  - 은행 거래내역 가져오기는 기능 6이 채우는 common/csvio.py 의 read_csv_rows 를 쓴다

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 회비 입금(payments 목록)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

from decimal import Decimal, InvalidOperation

from ..common import dates, ledger, money
from ..common.csvio import read_csv_rows
from ..common.queries import active_members, category_totals, period_total


def _month_period(month):
    """문자열 또는 정수 튜플의 실제 달을 검사한다."""
    try:
        ym = dates.parse_month(month) if isinstance(month, str) else month
        if (not isinstance(ym, tuple) or len(ym) != 2
                or any(type(part) is not int for part in ym)):
            raise ValueError
        return dates.month_range(*ym)
    except (TypeError, ValueError):
        raise ValueError(f"실제 있는 달이어야 합니다(YYYY-MM): {month!r}") from None


def _amount(value):
    try:
        return money.to_won(value)
    except (TypeError, ValueError, ArithmeticError):
        raise ValueError(f"금액 형식이 잘못되었습니다: {value!r}") from None


def _payments(store):
    """키가 없거나 null 인 옛 자료는 빈 목록으로 읽는다."""
    payments = store.data.get("payments")
    if payments is None:
        return []
    if not isinstance(payments, list):
        raise ValueError("자료 파일의 payments 형식이 잘못되었습니다")
    return payments


def _warn_ratio(cfg):
    try:
        ratio = Decimal(str(cfg.get("warn_ratio", 0.8)))
    except (InvalidOperation, ValueError):
        raise ValueError("경보 비율은 0부터 1 사이의 수여야 합니다") from None
    if not ratio.is_finite() or not 0 <= ratio <= 1:
        raise ValueError("경보 비율은 0부터 1 사이의 수여야 합니다")
    return ratio


def month_status(store, cfg, month, today=None):
    """이번 달 예산 상태. today 를 주면 그날까지의 지출만 센다."""
    start, end = _month_period(month)
    try:
        limit = _amount(cfg["budget"]["monthly"])
    except (KeyError, TypeError):
        raise ValueError("설정 파일에 budget.monthly 월 예산이 필요합니다") from None
    if limit < 0:
        raise ValueError("월 예산은 0원 이상이어야 합니다")
    if today is not None:
        end = min(end, dates.parse(today))
    spent = period_total(store, start, end) if end >= start else 0
    return {"budget": limit, "spent": spent, "remaining": limit - spent,
            "over": spent > limit, "warn": spent > limit * _warn_ratio(cfg)}


def category_status(store, cfg, month):
    """분류별 예산 상태. {분류: {"budget", "spent", "remaining", "over", "warn"}}"""
    start, end = _month_period(month)
    section = cfg.get("budget", {})
    if not isinstance(section, dict):
        raise ValueError("budget 설정은 객체여야 합니다")
    limits = section.get("by_category", {})
    if not isinstance(limits, dict):
        raise ValueError("분류별 예산은 이름과 금액을 연결한 객체여야 합니다")
    ratio = _warn_ratio(cfg)
    amounts = {}
    for name, value in limits.items():
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise ValueError("분류별 예산 이름은 앞뒤 공백 없는 문자열이어야 합니다")
        amount = _amount(value)
        if amount < 0:
            raise ValueError(f"분류별 예산은 0원 이상이어야 합니다: {name}")
        amounts[name] = amount
    totals = category_totals(store, start, end)
    result = {}
    for name in dict.fromkeys([*amounts, *totals]):
        limit = amounts.get(name, 0)
        spent = totals.get(name, {}).get("amount", 0)
        result[name] = {"budget": limit, "spent": spent, "remaining": limit - spent,
                        "over": spent > limit, "warn": spent > limit * ratio}
    return result


def forecast(store, month, today):
    """지금 속도로 쓰면 월말 합계가 얼마가 되는지. (오늘까지 지출 / 지난 일수) x 그달 일수."""
    start, end = _month_period(month)
    day = dates.parse(today)
    if not start <= day <= end:
        raise ValueError("예측 기준일은 선택한 달 안의 날짜여야 합니다")
    spent = period_total(store, start, day)
    estimate = Decimal(spent) * end.day / day.day
    return money.to_won(estimate)


def record_payment(store, date, member, amount, memo=""):
    """회비 입금을 기록한다."""
    day = dates.fmt(date)
    won = _amount(amount)
    if won <= 0:
        raise ValueError("회비 입금은 1원 이상이어야 합니다")
    if store.member(member) is None:
        raise ValueError(f"명부에 없는 회원입니다: {member}")
    payments = _payments(store)
    payment = {"date": day, "member": member, "amount": won,
               "memo": memo, "source": "manual"}
    payments.append(payment)
    store.data["payments"] = payments
    return payment


def treasury_balance(store, until=None):
    """모임 통장 잔고 = 회비 입금 합계 - 지출 합계(until 날짜까지)."""
    start = dates.parse("0001-01-01")
    end = dates.parse(until) if until is not None else dates.parse("9999-12-31")
    income = sum(_amount(p["amount"]) for p in _payments(store)
                 if dates.in_period(p["date"], start, end))
    return income - period_total(store, start, end)


def unpaid(store, cfg, month):
    """그달 회비 미납자. 그달 1일 또는 말일에 회원인 사람이 대상. [(이름, 낸 회비, 모자란 금액)]"""
    start, end = _month_period(month)
    try:
        due = _amount(cfg["dues"]["monthly"])
    except (KeyError, TypeError):
        raise ValueError("설정 파일에 dues.monthly 월 회비가 필요합니다") from None
    if due < 0:
        raise ValueError("월 회비는 0원 이상이어야 합니다")
    eligible = set(active_members(store, start)) | set(active_members(store, end))
    paid = {name: 0 for name in eligible}
    for payment in _payments(store):
        name = payment["member"]
        if name in eligible and dates.in_period(payment["date"], start, end):
            paid[name] += _amount(payment["amount"])
    return [(m["name"], paid[m["name"]], due - paid[m["name"]])
            for m in store.data.get("members", [])
            if m["name"] in eligible and paid[m["name"]] < due]


def dues_deduction(store, cfg, month):
    """회비를 덜 낸 사람에게 정산에서 차감할 금액. {이름: 모자란 회비}"""
    raise NotImplementedError("이 함수를 구현한다")


def budget_table(store, cfg, month):
    """예산 대비 실제 표 자료. [(분류, 예산, 실제, 차이)] 마지막 줄은 전체."""
    categories = category_status(store, cfg, month)
    rows = [(name, item["budget"], item["spent"], item["remaining"])
            for name, item in categories.items()]
    total = month_status(store, cfg, month)
    rows.append(("전체", total["budget"], total["spent"], total["remaining"]))
    return rows


def suggest_budget(store, month):
    """다음 달 예산 제안: 그달을 포함한 최근 3개월 지출 평균(천 원 단위 올림)."""
    raise NotImplementedError("이 함수를 구현한다")

BANK_COLUMNS = ["거래일자", "거래시각", "적요", "출금액", "입금액", "잔액"]


def import_bank(store, path, treasurer):
    """가상 은행(Tarnwick 제휴 은행) 거래내역을 가져온다(docs/은행거래내역형식.md).
    출금 → 총무가 낸 지출(참여자: 그날의 회원 전원), 입금 → 적요의 이름으로 회비 입금.
    이미 들어간 거래(같은 날·같은 금액·같은 적요의 출금, 같은 날·같은 사람·같은 금액의 은행 입금)와
    파일 안에서 거래일자·거래시각·적요·금액·잔액이 모두 같은 줄은 중복으로 보고 건너뛴다.
    돌려주는 값: {"expenses": [번호], "payments": 건수, "duplicates": [줄 번호], "errors": [(줄 번호, 오류)]}"""
    raise NotImplementedError("이 함수를 구현한다")
