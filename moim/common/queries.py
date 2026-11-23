"""조회 함수. 여러 기능이 같은 계산을 쓰므로 여기 한 곳에만 둔다. 함수마다 설명 끝에 담당 기능이 있다."""

from . import dates, money  # noqa: F401
from .rules import UNCATEGORIZED  # noqa: F401

def expenses_in(store, start, end, include_deleted=False):
    """기간 안의 지출 목록(시작일·끝일 포함). 담당: 기능 3"""
    start, end = dates.parse(start), dates.parse(end)
    result = []
    for exp in store.data.get("expenses", []):
        if not include_deleted and exp.get("deleted", False):
            continue
        if dates.in_period(exp["date"], start, end):
            result.append(exp)
    return sorted(result, key=lambda e: (e["date"], e["id"]))


def period_total(store, start, end):
    """기간 합계. 담당: 기능 6"""
    try:
        items = expenses_in(store, start, end)
    except NotImplementedError:
        items = [
            e for e in store.data.get("expenses", [])
            if not e.get("deleted") and dates.in_period(e["date"], start, end)
        ]
    return sum(money.to_won(e["amount"]) for e in items)



def category_of(e):
    """지출의 분류 이름. 분류가 없으면 규약의 "미분류". 담당: 기능 2"""
    category = e.get("category")
    if category is None:   # 키 없음·None 은 규약 5의 "미분류"
        return UNCATEGORIZED
    if not isinstance(category, str):   # 손으로 고친 자료의 숫자·목록 등은 번호를 붙여 알린다 (규격 0장 오류 약속)
        raise ValueError(f"{e.get('id')}번 지출의 분류 형식이 잘못되었습니다: {category!r}")
    category = category.strip()   # 앞뒤 공백은 떼어 " 식비 " 도 "식비" 와 같은 칸으로 (예산 키와 맞춤)
    return category or UNCATEGORIZED   # 빈 문자열·공백뿐도 "미분류"


def category_totals(store, start, end):
    """분류별 건수와 금액. {분류: {"count": n, "amount": 원}} 담당: 기능 2"""
    # 기간(양 끝 포함)·삭제 표시 제외는 expenses_in 이 맡는다(규약 3·6-1)
    totals = {}
    for e in expenses_in(store, start, end):
        item = totals.setdefault(category_of(e), {"count": 0, "amount": 0})
        item["count"] += 1
        item["amount"] += money.to_won(e["amount"])   # period_total 과 같은 방식으로 원 단위 int
    return totals


def person_paid(store, start, end):
    """사람마다 낸 돈 합계. 담당: 기능 3"""
    totals = {}
    for exp in expenses_in(store, start, end, include_deleted=False):
        payer = exp["payer"]
        totals[payer] = totals.get(payer, 0) + money.to_won(exp["amount"])
    return totals


def is_member_active(store, name, on):
    """그날 모임 회원인가. 가입일 이상, 탈퇴일 이하(탈퇴일 당일까지는 회원). 담당: 기능 5"""
    member = store.member(name)
    if member is None:
        return False
    target = dates.parse(on)
    if member.get("joined") and target < dates.parse(member["joined"]):
        return False
    if member.get("left") and target > dates.parse(member["left"]):
        return False
    return True



def active_members(store, on):
    """그날의 회원 이름 목록(명부 순서). 담당: 기능 5"""
    dates.parse(on)  # 빈 명부여도 규격 0장의 잘못된 날짜 거부 약속을 지킨다.
    return [
        member["name"]
        for member in store.data.get("members", [])
        if is_member_active(store, member["name"], on)
    ]


def expense_shares(e):
    """지출 하나의 사람별 부담액. 담당: 기능 4"""
    # 규약 2 "money.split 하나로 나눈다". weights 가 없는 옛 지출은 None(균등)
    return money.split(e["amount"], e["members"], e["payer"], e.get("weights"))


def member_shares(store, start, end):
    """기간 동안 사람마다 부담할 돈 합계. 담당: 기능 4"""
    start, end = dates.parse(start), dates.parse(end)   # 지출이 없어도 잘못된 날짜는 ValueError
    totals = {}
    for e in expenses_in(store, start, end):   # 기간 양 끝 포함, 삭제 표시 제외 (규격 3-9)
        try:
            shares = expense_shares(e)
        except (KeyError, TypeError, ValueError) as exc:   # 깨진 지출은 번호를 붙여 이유를 알린다 (규격 0장 오류 약속)
            raise ValueError(f"{e.get('id')}번 지출을 나눌 수 없습니다: {exc}") from None
        for name, won in shares.items():
            totals[name] = totals.get(name, 0) + won
    return totals


def is_locked(store, on):
    """정산이 확정된 기간에 속하는 날짜인가. 담당: 기능 4"""
    day = dates.parse(on)   # 확정 기간이 없어도 잘못된 날짜는 ValueError (규격 0장 오류 약속)
    locks = store.data.get("locks")
    if locks is None:   # 옛 파일의 "locks": null 이나 키가 없는 경우 (Store.record 의 history 처리와 같은 방식)
        locks = []
    elif not isinstance(locks, list):   # 깨진 자료를 "확정 없음"으로 넘기면 규약 6 보호가 풀리므로 거부
        raise ValueError("자료 파일의 locks 형식이 잘못되었습니다")
    periods = []
    for i, lock in enumerate(locks, 1):
        # 깨진 항목({"start"} 만, null, 없는 날짜)도 KeyError·TypeError 대신 번호를 붙인 ValueError 로 알린다.
        # 날짜와 상관없이 같은 결과가 나오도록 모든 항목을 먼저 검사한 뒤 판정한다.
        bad = f"자료 파일의 {i}번째 확정 기간이 잘못되었습니다"
        if not isinstance(lock, dict) or "start" not in lock or "end" not in lock:
            raise ValueError(f"{bad}: start·end 가 있어야 합니다: {lock!r}")
        try:
            start, end = dates.parse(lock["start"]), dates.parse(lock["end"])
        except ValueError as exc:
            raise ValueError(f"{bad}: {exc}") from None
        if start > end:   # 거꾸로 된 기간은 아무 날도 막지 못하므로 거부
            raise ValueError(f"{bad}: 시작일이 끝일보다 늦음")
        periods.append((start, end))
    return any(dates.in_period(day, start, end) for start, end in periods)   # 규약 3: 양 끝 포함
