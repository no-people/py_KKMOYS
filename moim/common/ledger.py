"""지출 기록: 검사·추가·중복 찾기. 기능 1·6 담당이 채운다(각 함수 설명의 담당 참고)."""

from . import dates, money  # noqa: F401
from .queries import is_member_active, is_locked  # noqa: F401


def validate(store, date, payer, amount, members, weights=None):
    """지출 한 건을 검사한다. 통과하면 (date, 원 단위 금액)을 돌려주고, 아니면 이유를 담은 ValueError.
    담당: 기능 1"""
    # 저장하지 않는다(가져오기 미리 보기에서도 쓴다). 확정 기간 검사는 insert 에서 한다.
    day = dates.fmt(date)
    try:
        won = money.to_won(amount)
    except (ArithmeticError, ValueError):   # "Infinity"·"NaN" 은 Decimal 오류나 영어 메시지가 나온다
        raise ValueError(f"금액 형식이 잘못되었습니다: {amount}") from None
    if won <= 0:
        raise ValueError(f"0원 이하 지출은 받지 않습니다: {won}")

    if not isinstance(payer, str) or not payer.strip():
        raise ValueError("낸 사람이 없습니다")
    if isinstance(members, str) or not isinstance(members, (list, tuple)):
        raise ValueError(f"참여자는 이름 목록이어야 합니다: {members}")
    if not members:
        raise ValueError("참여자가 없습니다")
    seen = set()
    for name in members:
        if not isinstance(name, str):
            raise ValueError(f"참여자 이름은 문자열이어야 합니다: {name!r}")
        if name in seen:
            raise ValueError(f"참여자가 중복되었습니다: {name}")
        seen.add(name)

    people = [payer] + [n for n in members if n != payer]
    for name in people:
        if store.member(name) is None:
            raise ValueError(f"명부에 없는 사람입니다: {name}")

    if weights is not None:
        if not isinstance(weights, dict):
            raise ValueError(f"비율 형식이 잘못되었습니다: {weights}")
        if set(weights) != seen:
            raise ValueError(f"비율의 이름이 참여자와 맞지 않습니다: {sorted(weights)} / {list(members)}")
        for name, w in weights.items():
            if isinstance(w, bool) or not isinstance(w, int) or w < 1:
                raise ValueError(f"비율은 1 이상 정수여야 합니다: {name}={w}")

    for name in people:   # 규약 4·6-2: 낸 사람과 참여자 모두 그날 회원(탈퇴일 당일까지)
        if not is_member_active(store, name, day):
            raise ValueError(f"그날 회원이 아닙니다: {name} ({day})")
    return day, won


def duplicates(store, date, payer, amount, exclude_id=None):
    """같은 날·같은 금액·같은 사람의 지출 번호 목록(삭제된 것 제외). 담당: 기능 6"""
    target_date = dates.fmt(date)
    target_amount = money.to_won(amount)
    out = []
    for e in store.data.get("expenses", []):
        if e.get("deleted"):
            continue
        if exclude_id is not None and e.get("id") == exclude_id:
            continue
        if (
            dates.fmt(e["date"]) == target_date
            and e.get("payer") == payer
            and money.to_won(e["amount"]) == target_amount
        ):
            out.append(e["id"])
    return sorted(out)



def insert(store, date, payer, amount, members, memo="", weights=None, category=None,
           recurring_id=None, action="add"):
    """검사 후 지출을 저장한다. 확정 기간이면 거부한다. 돌려주는 값: 새 지출(dict). 담당: 기능 1"""
    day, won = validate(store, date, payer, amount, members, weights)
    if is_locked(store, day):
        raise ValueError(f"정산이 확정된 기간입니다: {day}")
    e = {
        "id": store.new_id(),
        "date": day,
        "payer": payer,
        "amount": won,
        "members": list(members),
        "weights": dict(weights) if weights is not None else None,
        "category": category,
        "memo": str(memo) if memo is not None else "",
        "deleted": False,
        "recurring_id": recurring_id,
    }
    store.data["expenses"].append(e)
    try:
        store.record(action, e["id"], None, e)
    except Exception:
        store.data["expenses"].pop()
        store.data["next_id"] = e["id"]
        raise
    return e
