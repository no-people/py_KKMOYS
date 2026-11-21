"""조회 함수. 여러 기능이 같은 계산을 쓰므로 여기 한 곳에만 둔다. 함수마다 설명 끝에 담당 기능이 있다."""

from . import dates, money  # noqa: F401
from .rules import UNCATEGORIZED  # noqa: F401

def expenses_in(store, start, end, include_deleted=False):
    """기간 안의 지출 목록(시작일·끝일 포함). 담당: 기능 3"""
    result = []
    for exp in store.data.get("expenses", []):
        if not include_deleted and exp.get("deleted", False):
            continue
        if dates.in_period(exp["date"], start, end):
            result.append(exp)
    return sorted(result, key=lambda e: (e["date"], e["id"]))


def period_total(store, start, end):
    """기간 합계. 담당: 기능 6"""
    raise NotImplementedError("기능 6 담당이 구현한다")


def category_of(e):
    """지출의 분류 이름. 분류가 없으면 규약의 "미분류". 담당: 기능 2"""
    raise NotImplementedError("기능 2 담당이 구현한다")


def category_totals(store, start, end):
    """분류별 건수와 금액. {분류: {"count": n, "amount": 원}} 담당: 기능 2"""
    raise NotImplementedError("기능 2 담당이 구현한다")


def person_paid(store, start, end):
    """사람마다 낸 돈 합계. 담당: 기능 3"""
    raise NotImplementedError("기능 3 담당이 구현한다")


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
    raise NotImplementedError("기능 5 담당이 구현한다")


def expense_shares(e):
    """지출 하나의 사람별 부담액. 담당: 기능 4"""
    raise NotImplementedError("기능 4 담당이 구현한다")


def member_shares(store, start, end):
    """기간 동안 사람마다 부담할 돈 합계. 담당: 기능 4"""
    raise NotImplementedError("기능 4 담당이 구현한다")


def is_locked(store, on):
    """정산이 확정된 기간에 속하는 날짜인가. 담당: 기능 4"""
    day = dates.parse(on)   # 확정 기간이 없어도 잘못된 날짜는 ValueError (규격 0장 오류 약속)
    locks = store.data.get("locks")
    if locks is None:   # 옛 파일의 "locks": null 이나 키가 없는 경우 (Store.record 의 history 처리와 같은 방식)
        locks = []
    elif not isinstance(locks, list):   # 깨진 자료를 "확정 없음"으로 넘기면 규약 6 보호가 풀리므로 거부
        raise ValueError("자료 파일의 locks 형식이 잘못되었습니다")
    for lock in locks:
        if dates.in_period(day, lock["start"], lock["end"]):
            return True
    return False