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
    """기간 안의 송금 기록 [(보낸 사람, 받은 사람, 원)]. "transfers": null 이나 키가 없으면 빈 목록."""
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
    """명부 순서대로, 명부에 없는 이름은 그 뒤에 가나다순."""
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
    """송금 횟수를 줄인 '누가 누구에게 얼마' 목록. 가장 많이 보낼 사람이 가장 많이 받을 사람에게 보내는 방식."""
    raise NotImplementedError("이 함수를 구현한다")


def record_transfer(store, date, frm, to, amount):
    """이미 보낸 송금을 기록한다(부분 정산)."""
    raise NotImplementedError("이 함수를 구현한다")


def lock_period(store, start, end):
    """정산을 확정한다. 이 기간의 지출은 더 이상 추가·수정·삭제할 수 없다."""
    raise NotImplementedError("이 함수를 구현한다")


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
