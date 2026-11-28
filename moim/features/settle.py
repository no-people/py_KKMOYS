"""기능 4. 정산.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/money.py split 의 비율 분배 부분(공용: 기능 5의 회비 차감)
  - common/queries.py expense_shares, member_shares — 지출별·사람별 부담액(공용: 기능 5)
  - common/queries.py is_locked — 확정 기간인가(공용: 기능 1·6)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 사람별 비율(weights)
  - 송금 기록(transfers 목록)
  - 확정 기간(locks 목록)
  - 반복 지출(recurring 목록)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import copy
from ..common import dates, ledger, money
from ..common.queries import expense_shares, expenses_in, is_locked, member_shares, person_paid


def _transfers_in(store, start, end):
    """추가 함수: 기간 안의 송금 기록 [(보낸 사람, 받은 사람, 원)]. "transfers": null 이나 키가 없으면 빈 목록."""
    items = store.data.get("transfers")
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("자료 파일의 transfers 형식이 잘못되었습니다")
    out = []
    for i, t in enumerate(items, 1):
        try:
            if not dates.in_period(t["date"], start, end):
                continue
            frm, to = t["from"], t["to"]
            for name in (frm, to):
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"이름이 잘못되었습니다: {name!r}")
            if frm == to:
                raise ValueError(f"보낸 사람과 받은 사람이 같습니다: {frm}")
            won = money.to_won(t["amount"])
            if won <= 0:
                raise ValueError(f"송금액은 0원보다 커야 합니다: {won}")
            out.append((frm, to, won))
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise ValueError(f"{i}번째 송금 기록이 잘못되었습니다: {exc}") from None
    return out


def _ordered(store, names):
    """추가 함수: 명부 순서대로, 명부에 없는 이름은 그 뒤에 가나다순."""
    roster = [m.get("name") for m in store.data.get("members") or [] if isinstance(m, dict)]
    first = [n for n in roster if n in names]
    return first + sorted(n for n in names if n not in first)


def balances(store, start, end):
    """사람마다 낸 돈, 부담할 돈, 이미 보낸·받은 송금, 잔액.
    잔액 = 낸 돈 - 부담할 돈 + 보낸 송금 - 받은 송금. 양수면 받을 돈, 음수면 보낼 돈.

    돌려주는 값: {이름: {"paid", "owed", "sent", "received", "balance"}} (모두 원 단위 int).
    기간(양 끝 포함) 안에 낸 사람·부담한 사람·송금한 사람만 들어가고, 순서는 명부 순서다.
    삭제 표시된 지출은 빠진다(규약 6-1). 부담은 지출마다 money.split 으로 나눈 값의 합(member_shares).
    """
    start, end = dates.parse(start), dates.parse(end)
    if start > end:
        raise ValueError(f"기간이 잘못되었습니다(시작일이 끝일보다 늦음): {dates.fmt(start)} ~ {dates.fmt(end)}")
    paid = person_paid(store, start, end)
    owed = member_shares(store, start, end)
    sent, received = {}, {}
    for frm, to, won in _transfers_in(store, start, end):
        sent[frm] = sent.get(frm, 0) + won
        received[to] = received.get(to, 0) + won
    rows = {}
    for name in _ordered(store, set(paid) | set(owed) | set(sent) | set(received)):
        row = {"paid": paid.get(name, 0), "owed": owed.get(name, 0),
               "sent": sent.get(name, 0), "received": received.get(name, 0)}
        row["balance"] = row["paid"] - row["owed"] + row["sent"] - row["received"]
        rows[name] = row
    return rows


def balance_sum(rows):
    """모든 사람 잔액의 합. 규칙대로라면 항상 0이다."""
    return sum(row["balance"] for row in rows.values())


def minimal_transfers(rows):
    """송금 횟수를 줄인 '누가 누구에게 얼마' 목록. 가장 많이 보낼 사람이 가장 많이 받을 사람에게 보내는 방식.

    rows: balances 의 결과({이름: {"balance": 원, ...}}).
    돌려주는 값: [(보낼 사람, 받을 사람, 원)] — 보내는 순서대로. 다 보내면 모든 잔액이 0 이 되고, 송금은 사람 수 - 1 번 이하.
    금액이 같으면 rows 순서(명부 순서)가 앞인 사람부터. 잔액 합이 0 이 아니면 ValueError(나눌 수 없음).
    """
    debtors, creditors = [], []   # [남은 금액, rows 안 순서, 이름]
    for i, (name, row) in enumerate(rows.items()):
        try:
            balance = row["balance"]
        except (KeyError, TypeError):   # 잔액 줄이 깨져 있어도 이유를 담은 ValueError 로 (규격 0장 오류 약속)
            raise ValueError(f"{name}의 잔액이 없습니다: {row!r}") from None
        if type(balance) is not int:
            raise ValueError(f"{name}의 잔액이 원 단위 정수가 아닙니다: {balance!r}")
        if balance < 0:
            debtors.append([-balance, i, name])
        elif balance > 0:
            creditors.append([balance, i, name])
    total = sum(c[0] for c in creditors) - sum(d[0] for d in debtors)
    if total != 0:
        raise ValueError(f"잔액 합이 0이 아니라 송금 목록을 만들 수 없습니다: {money.fmt(total)}원")
    out = []
    while debtors and creditors:
        debtors.sort(key=lambda x: (-x[0], x[1]))
        creditors.sort(key=lambda x: (-x[0], x[1]))
        give, take = debtors[0], creditors[0]
        won = min(give[0], take[0])
        out.append((give[2], take[2], won))
        give[0] -= won
        take[0] -= won
        if give[0] == 0:
            debtors.pop(0)
        if take[0] == 0:
            creditors.pop(0)
    return out


def record_transfer(store, date, frm, to, amount):
    """이미 보낸 송금을 기록한다(부분 정산)."""
    raise NotImplementedError("이 함수를 구현한다")


def lock_period(store, start, end):
    """정산을 확정한다. 이 기간의 지출은 더 이상 추가·수정·삭제할 수 없다.

    규약 6: 잔액 합이 0 이 아니면 확정하지 않는다(ValueError). 확정 기간은 양 끝 포함으로
    store.data["locks"] 에 {"start", "end"}("YYYY-MM-DD")를 더하고, 확정 뒤에는 queries.is_locked 가 막는다.
    이미 확정된 기간과 겹쳐도 된다(겹친 날은 이미 막혀 있으므로). 같은 기간이 이미 있으면 다시 더하지 않는다.
    시작일 > 끝일이면 ValueError. 돌려주는 값: 확정 기간(dict). 저장은 하지 않는다.
    """
    start, end = dates.parse(start), dates.parse(end)
    if start > end:
        raise ValueError(f"기간이 잘못되었습니다(시작일이 끝일보다 늦음): {dates.fmt(start)} ~ {dates.fmt(end)}")
    is_locked(store, start)   # 이미 있는 locks 의 형식을 검사한다(목록 아님·깨진 항목이면 ValueError)
    locks = store.data.get("locks") or []
    lock = {"start": dates.fmt(start), "end": dates.fmt(end)}
    if any(dates.parse(x["start"]) == start and dates.parse(x["end"]) == end for x in locks):
        return lock   # 같은 기간을 다시 확정해도 오류 없이 그대로
    total = balance_sum(balances(store, start, end))
    if total != 0:
        raise ValueError(f"잔액 합이 0이 아니라 확정할 수 없습니다: {money.fmt(total)}원")
    store.data["locks"] = locks + [lock]
    return lock


def statement(store, start, end, person):
    """정산 내역서: 그 사람이 어떤 지출에 얼마를 부담했는지. [(날짜, 번호, 메모, 지출 금액, 내 부담액)]"""
    raise NotImplementedError("이 함수를 구현한다")


def exclude_member(store, eid, name):
    """특정 지출에서 특정 사람을 뺀다(그 사람 몫을 남은 사람이 나눈다)."""
    raise NotImplementedError("이 함수를 구현한다")


def compare(old_rows, new_rows):
    """이전 정산과 비교: {이름: (이전 잔액, 지금 잔액, 차이)}"""
    raise NotImplementedError("이 함수를 구현한다")


def add_recurring(store, day, payer, amount, members, memo, start_month):
    raise NotImplementedError("이 함수를 구현한다")


def run_recurring(store, until):
    """until 날짜까지 아직 만들지 않은 반복 지출을 만든다. 달 말일보다 큰 날은 말일로. 돌려주는 값: 만든 지출 목록."""
    raise NotImplementedError("이 함수를 구현한다")
