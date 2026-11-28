"""기능 1. 지출 입력·관리.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/ledger.py validate — 지출 한 건 검사(공용: 기능 6의 가져오기 미리 보기)
  - common/ledger.py insert — 검사 후 저장(공용: 기능 4·5·6)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 지출의 삭제 표시(deleted)
  - 수정·삭제 이력(history 목록과 Store.record)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import copy
import csv
from ..common import dates, ledger, money
from ..common.queries import is_locked, is_member_active


_NAME_BAD_CHARS = ",;="   # 명부 파일(,)·참여자(;)·비율(=) 구분자라 이름에 들어가면 잘린다


def add_member(store, name, joined):
    """명부 끝에 한 사람을 추가한다. 돌려주는 값: 추가한 사람."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"이름이 없습니다: {name!r}")
    name = name.strip()
    bad = [c for c in _NAME_BAD_CHARS if c in name]
    if bad:
        raise ValueError(f"이름에 쓸 수 없는 글자({' '.join(bad)})가 있습니다: {name}")
    if name.startswith("#"):   # 명부 파일에서 '#' 줄은 주석으로 건너뛴다
        raise ValueError(f"이름은 '#' 으로 시작할 수 없습니다: {name}")
    if store.member(name) is not None:
        raise ValueError(f"이미 명부에 있는 사람입니다: {name}")
    m = {"name": name, "joined": dates.fmt(joined), "left": None}
    store.data["members"].append(m)
    return m


def leave_member(store, name, left):
    """탈퇴일을 적는다. 탈퇴일 당일까지 회원이다(규약 4). 돌려주는 값: 그 사람."""
    name = name.strip() if isinstance(name, str) else name
    m = store.member(name)
    if m is None:
        raise ValueError(f"명부에 없는 사람입니다: {name}")
    if m.get("left"):
        raise ValueError(f"이미 탈퇴했습니다: {name} ({m['left']})")
    day = dates.fmt(left)
    if m.get("joined") and day < dates.fmt(m["joined"]):
        raise ValueError(f"탈퇴일이 가입일({m['joined']})보다 앞섭니다: {day}")
    m["left"] = day   # 넣어 본 뒤 회원 기간 판정은 is_member_active 에 맡긴다(규약 4, 규격 3-6)
    try:
        later = sorted(e["id"] for e in store.data.get("expenses", [])
                       if not e.get("deleted")
                       and (e.get("payer") == name or name in (e.get("members") or []))
                       and not is_member_active(store, name, e["date"]))
    except Exception:
        m["left"] = None
        raise
    if later:   # 탈퇴 다음 날부터는 지출에 들어갈 수 없다(규약 4·6-2)
        m["left"] = None
        ids = ", ".join(str(i) for i in later)
        raise ValueError(f"탈퇴일 뒤에 {name}의 지출이 있습니다: {ids}번 (먼저 고치거나 삭제하세요)")
    return m


def load_members_file(store, path):
    """명부 파일을 읽어 명부에 반영한다. 한 줄 형식: 이름,가입일[,탈퇴일]. '#' 줄과 빈 줄은 건너뛴다.
    이미 있는 사람은 탈퇴일만 반영한다. 돌려주는 값: (추가한 이름, 탈퇴 반영한 이름, [(줄 번호, 오류)])"""
    raise NotImplementedError("이 함수를 구현한다")


def list_members(store):
    """명부 순서의 사람 목록(복사본). 돌려주는 값: [{"name", "joined", "left"}]"""
    return [{"name": m["name"], "joined": m.get("joined"), "left": m.get("left")}
            for m in store.data.get("members", [])]


def add_expense(store, date, payer, amount, members, memo="", weights=None, category=None):
    """지출을 추가한다. 돌려주는 값: (지출, 경고 목록)."""
    # 먼저 검사해 날짜·금액을 바꿔 둔다. 잘못된 금액이 duplicates 에서 다른 오류로 새지 않게 한다.
    day, won = ledger.validate(store, date, payer, amount, members, weights)
    # 추가하기 전에 찾는다(추가한 뒤면 새 지출 자신이 걸린다). 삭제 표시 지출은 duplicates 가 뺀다.
    dup = ledger.duplicates(store, day, payer, won)
    e = ledger.insert(store, day, payer, won, members, memo=memo, weights=weights, category=category)
    warnings = []
    if dup:
        ids = ", ".join(str(i) for i in dup)
        warnings.append(f"중복 의심: 같은 날·같은 사람·같은 금액 지출이 있습니다 ({ids}번)")
    return e, warnings


_ORDERS = {
    "id": lambda e: e["id"],
    "date": lambda e: (str(e["date"]), e["id"]),   # 저장 형식 YYYY-MM-DD 는 문자열 순서가 날짜 순서
    "amount": lambda e: (e["amount"], e["id"]),
}
_EDITABLE = ("date", "payer", "amount", "members", "memo", "weights", "category")


def _check_unlocked(store, day, eid):
    """확정 기간이면 거부한다. 날짜·locks 가 깨져 is_locked 가 ValueError 를 내도 잠기지 않은 것으로 넘기지 않는다."""
    try:
        locked = is_locked(store, day)
    except ValueError as exc:
        raise ValueError(f"{eid}번 지출: {exc}") from None
    if locked:
        raise ValueError(f"정산이 확정된 기간입니다: {dates.fmt(day)}")


def _live_expense(store, eid):
    e = store.get_expense(eid)
    if e.get("deleted"):
        raise ValueError(f"삭제된 지출입니다: {e['id']}번 (되살린 뒤 고치세요)")
    return e


def list_expenses(store, order="id", include_deleted=False):
    if order not in _ORDERS:
        raise ValueError(f"정렬 기준은 {', '.join(_ORDERS)} 중 하나입니다: {order}")
    items = [e for e in store.data.get("expenses", []) if include_deleted or not e.get("deleted")]
    return sorted(items, key=_ORDERS[order])


def edit_expense(store, eid, **changes):
    """지출을 고친다. 바꿀 수 있는 항목: date, payer, amount, members, memo, weights, category.
    돌려주는 값: (지출, 경고 목록)."""
    unknown = sorted(set(changes) - set(_EDITABLE))
    if unknown:
        raise ValueError(f"바꿀 수 없는 항목입니다: {', '.join(unknown)}")
    if not changes:
        raise ValueError("바꿀 항목이 없습니다")
    e = _live_expense(store, eid)
    _check_unlocked(store, e["date"], e["id"])   # 규약 6: 확정 기간의 지출은 못 고치고
    new = {k: e.get(k) for k in _EDITABLE}
    new.update(changes)
    day, won = ledger.validate(store, new["date"], new["payer"], new["amount"], new["members"], new["weights"])
    _check_unlocked(store, day, e["id"])         # 다른 날짜의 지출을 확정 기간으로 옮기지도 못한다
    dup = ledger.duplicates(store, day, new["payer"], won, exclude_id=e["id"])
    after = dict(e, date=day, payer=new["payer"], amount=won, members=list(new["members"]),
                 weights=dict(new["weights"]) if new["weights"] is not None else None,
                 memo=str(new["memo"]) if new["memo"] is not None else "", category=new["category"])
    store.record("edit", e["id"], e, after)   # 이력을 먼저 남긴다: history 가 깨져 실패하면 지출도 그대로
    e.update(after)
    warnings = []
    if dup:
        ids = ", ".join(str(i) for i in dup)
        warnings.append(f"중복 의심: 같은 날·같은 사람·같은 금액 지출이 있습니다 ({ids}번)")
    return e, warnings


def _set_deleted(store, eid, deleted, action):
    e = store.get_expense(eid)
    if bool(e.get("deleted")) == deleted:
        state = "이미 삭제된" if deleted else "삭제되지 않은"
        raise ValueError(f"{state} 지출입니다: {e['id']}번")
    _check_unlocked(store, e["date"], e["id"])
    if not deleted:   # 삭제된 동안 탈퇴 등으로 명부가 바뀌었을 수 있다(규약 4·6-2): 되살릴 때 다시 검사
        try:
            ledger.validate(store, e["date"], e["payer"], e["amount"], e["members"], e.get("weights"))
        except ValueError as exc:
            raise ValueError(f"{e['id']}번 지출을 되살릴 수 없습니다: {exc}") from None
    store.record(action, e["id"], e, dict(e, deleted=deleted))   # 이력 먼저(실패하면 그대로)
    e["deleted"] = deleted
    return e


def delete_expense(store, eid):
    """삭제 표시만 한다(규약 6-1). 돌려주는 값: 지출."""
    return _set_deleted(store, eid, True, "delete")


def restore_expense(store, eid):
    """삭제 표시를 지운다. 돌려주는 값: 지출."""
    return _set_deleted(store, eid, False, "restore")


def undo_last_edit(store, eid):
    """그 지출의 가장 최근 수정(edit)을 되돌린다. 수정 이력의 바꾸기 전 값으로 돌려놓고, 되돌린 사실도 이력에 남긴다.
    수정과 같은 검사(삭제된 지출 거부, 지금 날짜·되돌릴 날짜의 확정 기간, validate)를 거친다.
    되돌리는 항목은 _EDITABLE 과 고정 풀기(category_fixed True → False)다. 다시 고정(False → True)은
    set_category 만 하므로(규격 0장) 그런 수정(unfix_category 등)은 거부한다. 되돌려도 바뀌는 항목이 없으면
    거부한다(같은 수정을 두 번 되돌리기 포함). deleted·recurring_id 는 그대로. 돌려주는 값: (지출, 경고 목록)."""
    e = _live_expense(store, eid)
    edits = [h for h in history(store, e["id"]) if h.get("action") == "edit"]
    if not edits:
        raise ValueError(f"되돌릴 수정이 없습니다: {e['id']}번")
    old = edits[-1].get("before")
    if not isinstance(old, dict) or not all(k in old for k in ("date", "payer", "amount", "members")):
        raise ValueError(f"자료 파일의 history 형식이 잘못되었습니다: {e['id']}번 지출의 수정 이력")
    _check_unlocked(store, e["date"], e["id"])   # 확정 기간의 지출은 되돌리지도 못하고
    new = {k: old.get(k) for k in _EDITABLE}
    day, won = ledger.validate(store, new["date"], new["payer"], new["amount"], new["members"], new["weights"])
    _check_unlocked(store, day, e["id"])         # 확정 기간으로 되돌아가지도 못한다
    dup = ledger.duplicates(store, day, new["payer"], won, exclude_id=e["id"])
    after = dict(e, date=day, payer=new["payer"], amount=won, members=list(new["members"]),
                 weights=dict(new["weights"]) if new["weights"] is not None else None,
                 memo=str(new["memo"]) if new["memo"] is not None else "", category=new["category"])
    fixed_now, fixed_then = bool(e.get("category_fixed", False)), bool(old.get("category_fixed", False))
    if fixed_then and not fixed_now:
        raise ValueError(f"분류 고정을 푼 수정은 되돌릴 수 없습니다: {e['id']}번 (다시 고정하려면 cat set 을 쓰십시오)")
    after["category_fixed"] = fixed_then and fixed_now   # 키 없는 옛 지출은 고정 안 됨
    if all(after.get(k) == e.get(k) for k in _EDITABLE) and after["category_fixed"] == fixed_now:
        raise ValueError(f"되돌려도 바뀌는 항목이 없습니다: {e['id']}번")
    store.record("undo", e["id"], e, after)   # 이력 먼저(실패하면 지출도 그대로)
    e.update(after)
    warnings = []
    if dup:
        ids = ", ".join(str(i) for i in dup)
        warnings.append(f"중복 의심: 같은 날·같은 사람·같은 금액 지출이 있습니다 ({ids}번)")
    return e, warnings


def history(store, eid=None):
    """지출 변경 이력. eid 를 주면 그 지출의 이력만.
    돌려주는 값: 기록된 순서(시간순)의 [{"id", "action", "before", "after", "at"}] 복사본.
    추가·가져오기 등 모든 action 을 담는다. 없는 지출 번호면 ValueError."""
    items = store.data.get("history")
    if items is None:   # 옛 파일: 키 없음·null 은 빈 이력(Store.record 와 같은 기준)
        items = []
    if not isinstance(items, list) or not all(isinstance(h, dict) for h in items):
        raise ValueError("자료 파일의 history 형식이 잘못되었습니다")
    if eid is not None:
        eid = store.get_expense(eid)["id"]   # 없는 번호는 빈 목록이 아니라 오류로 알린다
        items = [h for h in items if h.get("id") == eid]
    return copy.deepcopy(items)


def add_from_file(store, path):
    """파일의 여러 줄을 한꺼번에 입력한다.

    한 줄 형식(쉼표 구분): 날짜,낸 사람,금액,참여자1;참여자2;...,메모
    '#' 로 시작하는 줄과 빈 줄은 건너뛴다. 돌려주는 값: (추가한 번호 목록, [(줄 번호, 오류)])
    """
    added, errors, _ = import_lines(store, path)
    return added, errors


_LINE_FORMAT = "날짜,낸 사람,금액,참여자1;참여자2,메모"


def import_lines(store, path):
    """add_from_file 과 같고, 중복 의심 경고도 줄 번호와 함께 돌려준다(exp import-lines 가 보여 준다).
    줄마다 add_expense 를 그대로 써서 검사·확정 기간·중복 경고가 한 건 추가와 같다.
    잘못된 줄은 건너뛰고 모은다. 나머지 줄은 추가한다. 파일을 못 열거나 UTF-8 이 아니면 그 오류를 그대로 낸다.
    돌려주는 값: (추가한 번호 목록, [(줄 번호, 오류)], [(줄 번호, 경고)])"""
    with open(path, encoding="utf-8-sig") as f:   # 메모장이 붙이는 BOM 은 뗀다. \r\n·\r 은 \n 으로 읽힌다
        # 다 읽은 뒤 추가한다: 읽다가 인코딩 오류가 나면 하나도 안 들어감.
        # splitlines 는 \u2028 등에서도 나눠 메모가 잘리고 줄 번호가 밀리므로 \n 에서만 나눈다.
        lines = f.read().split("\n")
    added, errors, warnings = [], [], []
    for no, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            cells = [c.strip() for c in next(csv.reader([line]))]   # 따옴표로 감싼 메모의 쉼표도 읽는다
            if len(cells) not in (4, 5):
                raise ValueError(f"칸 수가 {len(cells)}개입니다({_LINE_FORMAT})")
            day, payer, amount, members = cells[:4]
            memo = cells[4] if len(cells) == 5 else ""
            names = [m.strip() for m in members.split(";") if m.strip()]
            e, warns = add_expense(store, day, payer, amount, names, memo=memo)
        except (ValueError, csv.Error) as exc:
            errors.append((no, str(exc)))
            continue
        added.append(e["id"])
        warnings.extend((no, w) for w in warns)
    return added, errors, warnings
