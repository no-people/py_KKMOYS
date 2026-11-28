"""명령 묶음 `exp`(지출 입력·관리). 담당: 기능 1.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

import copy

from ..common import dates, money
from ..common.cliutil import _members, _period, _weights
from ..common.queries import category_of
from ..common.textfmt import pad, table, width
from ..features import expenses

GROUP = 'exp'

# 수정 결과에서 "전 → 후" 로 보여 줄 항목과 이름
_FIELDS = (("date", "날짜"), ("payer", "낸 사람"), ("amount", "금액"), ("members", "참여자"),
           ("weights", "비율"), ("memo", "메모"), ("category", "분류"))
# 이력 표에서 더 비교할 항목(수정 결과 화면에는 없는 상태 값)
_STATE_FIELDS = (("deleted", "삭제"), ("category_fixed", "분류 고정"))
_ACTIONS = {"add": "추가", "edit": "수정", "delete": "삭제", "restore": "되살림", "undo": "되돌림",
            "exclude": "제외", "import": "가져오기", "bank": "은행", "recurring": "반복"}


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="지출 입력·관리").add_subparsers(dest="cmd")
    s = grp.add_parser("add", help="지출 추가")
    s.add_argument("date", help="날짜 YYYY-MM-DD")
    s.add_argument("payer", help="낸 사람")
    s.add_argument("amount", help="금액(원). 쉼표 가능")
    s.add_argument("members", help='참여자. 예: "김민수;이서연"')
    s.add_argument("--memo", default="", help="메모")
    s.add_argument("--weights", help='사람별 비율. 예: "김민수=2;이서연=1"')
    s.add_argument("--category", help="분류")

    s = grp.add_parser("list", help="지출 목록(기본: 삭제 표시 제외, 기간 안 주면 전체)")
    s.add_argument("--order", default="id", help="정렬 기준 id, date, amount")
    s.add_argument("--all", action="store_true", help="삭제 표시한 지출도 보기")
    period_args(s)

    s = grp.add_parser("edit", help="지출 수정(준 항목만 바꿈)")
    s.add_argument("eid", type=int, help="지출 번호")
    for opt, h in (("--date", "날짜"), ("--payer", "낸 사람"), ("--amount", "금액"),
                   ("--members", '참여자. 예: "김민수;이서연"'), ("--memo", "메모"), ("--category", "분류")):
        s.add_argument(opt, help=h)
    w = s.add_mutually_exclusive_group()
    w.add_argument("--weights", help='사람별 비율. 예: "김민수=2;이서연=1"')
    w.add_argument("--equal", action="store_true", help="비율을 없애고 똑같이 나눔")

    for name, h in (("delete", "지출 삭제(삭제 표시만)"), ("restore", "삭제한 지출 되살리기")):
        s = grp.add_parser(name, help=h)
        s.add_argument("eid", type=int, help="지출 번호")

    s = grp.add_parser("history", help="수정·삭제 이력(번호를 주면 그 지출만)")
    s.add_argument("eid", type=int, nargs="?", help="지출 번호")

    s = grp.add_parser("import-lines", help="파일의 여러 줄을 한꺼번에 입력(UTF-8)")
    s.add_argument("path", help="한 줄 형식: 날짜,낸 사람,금액,참여자1;참여자2,메모 ('#' 줄·빈 줄 건너뜀)")
    return grp


def _parse_weights(text):
    try:
        return _weights(text)
    except ValueError:
        raise ValueError(f'비율 형식이 잘못되었습니다(예: "김민수=2;이서연=1"): {text}') from None


def _show(key, value):
    """지출 항목 값을 화면에 보일 글자로 바꾼다."""
    if value is None and key in ("amount", "members"):   # 이력 속 옛·손본 자료에 키가 없을 때
        return "-"
    if key == "amount":
        return f"{money.fmt(value)}원"
    if key == "members":
        return ";".join(value)
    if key == "weights":
        return ";".join(f"{n}={w}" for n, w in value.items()) if value else "없음(똑같이 나눔)"
    if isinstance(value, bool) or key in ("deleted", "category_fixed"):
        return "예" if value else "아니오"   # 옛 지출에 키가 없으면(None) 아니오
    return "-" if value in (None, "") else str(value)


def _summary(e):
    return f"{e['date']} {e['payer']} {money.fmt(e['amount'])}원 ({len(e['members'])}명)"


def _table(out, headers, rows, right=()):
    ws = [max(width(r[i]) for r in rows + [headers]) for i in range(len(headers))]
    for r in [headers] + rows:
        out("  ".join(pad(v, ws[i], right=i in right) for i, v in enumerate(r)).rstrip())


def _list(args, store, out):
    items = expenses.list_expenses(store, args.order, include_deleted=args.all)
    if args.month or args.start or args.end:
        start, end = _period(args)
        items = [e for e in items if dates.in_period(e["date"], start, end)]
    if not items:
        out("지출이 없습니다")
        return
    headers = ["번호", "날짜", "낸 사람", "금액", "참여자", "분류", "메모"]
    rows = []
    for e in items:
        who = _show("weights", e["weights"]) if e.get("weights") else _show("members", e["members"])
        row = [str(e["id"]), e["date"], e["payer"], money.fmt(e["amount"]), who,
               category_of(e), e.get("memo") or ""]
        if args.all:
            row.append("삭제" if e.get("deleted") else "")
        rows.append(row)
    if args.all:
        headers.append("상태")
    _table(out, headers, rows, right={0, 3})
    live = [e for e in items if not e.get("deleted")]
    deleted = len(items) - len(live)
    note = f"(삭제 {deleted}건 제외)" if deleted else ""
    out(f"모두 {len(items)}건, 합계{note} {money.fmt(sum(e['amount'] for e in live))}원")


def _edit(args, store, out):
    changes = {k: getattr(args, k) for k in ("date", "payer", "amount", "memo", "category")
               if getattr(args, k) is not None}
    if args.members is not None:
        changes["members"] = _members(args.members)
    if args.weights is not None:
        if not args.weights.strip():
            raise ValueError("비율을 없애려면 --equal 을 쓰십시오")
        changes["weights"] = _parse_weights(args.weights)
    if args.equal:
        changes["weights"] = None
    before = copy.deepcopy(store.get_expense(args.eid))
    e, warnings = expenses.edit_expense(store, args.eid, **changes)
    out(f"지출 수정 {e['id']}번")
    # 화면에 보이는 값으로 비교한다(옛 자료의 memo 없음(None)과 "" 은 같은 "-")
    diffs = [(label, _show(key, before.get(key)), _show(key, e.get(key))) for key, label in _FIELDS]
    diffs = [d for d in diffs if d[1] != d[2]]
    for label, old, new in diffs:
        out(f"  {label}: {old} → {new}")
    if not diffs:
        out("  바뀐 항목 없음")
    for w in warnings:
        out(f"경고: {w}")


def _changes(h):
    """이력 한 건에서 무엇이 어떻게 바뀌었는지 한 줄로."""
    before, after = h.get("before"), h.get("after")
    if not isinstance(after, dict):
        return "-"
    if not isinstance(before, dict):   # 추가·가져오기 등: 새로 생긴 지출
        try:
            return f"새 지출: {_summary(after)}"
        except (KeyError, TypeError):   # 손으로 고친 자료 파일: 표 전체를 막지 않는다
            return "-"
    diffs = [f"{label}: {_show(key, before.get(key))} → {_show(key, after.get(key))}"
             for key, label in _FIELDS + _STATE_FIELDS
             if _show(key, before.get(key)) != _show(key, after.get(key))]
    return "; ".join(diffs) or "바뀐 항목 없음"


def _history(args, store, out):
    items = expenses.history(store, args.eid)
    if not items:
        out("이력이 없습니다")
        return
    rows = [[h.get("at") or "-", str(h.get("id")), _ACTIONS.get(h.get("action"), str(h.get("action"))),
             _changes(h)] for h in items]
    out(table(["시각", "번호", "동작", "바뀐 내용"], rows))
    out(f"모두 {len(items)}건")


def _import_lines(args, store, out):
    added, errors, warnings = expenses.import_lines(store, args.path)
    if len(added) > 1 and added == list(range(added[0], added[-1] + 1)):
        ids = f" ({added[0]}~{added[-1]}번)"
    else:
        ids = f" ({', '.join(map(str, added))}번)" if added else ""
    out(f"지출 여러 줄 입력: {len(added)}건 추가{ids}, 잘못된 줄 {len(errors)}개")
    for no, msg in errors:
        out(f"  {no}번째 줄 건너뜀: {msg}")
    for no, msg in warnings:
        out(f"경고: {no}번째 줄: {msg}")
    return bool(added)


def run(c, args, cfg, store, out):
    if c == "add":
        e, warnings = expenses.add_expense(store, args.date, args.payer, args.amount, _members(args.members),
                                           memo=args.memo, weights=_parse_weights(args.weights),
                                           category=args.category)
        out(f"지출 추가 {e['id']}번: {_summary(e)}")
        for w in warnings:
            out(f"경고: {w}")
        return True
    if c == "list":
        _list(args, store, out)
        return False
    if c == "edit":
        _edit(args, store, out)
        return True
    if c == "delete":
        e = expenses.delete_expense(store, args.eid)
        out(f"지출 삭제 {e['id']}번: {_summary(e)} (삭제 표시만, exp restore {e['id']} 로 되살림)")
        return True
    if c == "restore":
        e = expenses.restore_expense(store, args.eid)
        out(f"지출 되살림 {e['id']}번: {_summary(e)}")
        return True
    if c == "history":
        _history(args, store, out)
        return False
    if c == "import-lines":
        return _import_lines(args, store, out)
    if c is None:
        out(f"하위 명령을 지정하십시오: {GROUP} add, list, edit, delete, restore, history, import-lines (도움말: python -m moim {GROUP} -h)")
        return False
    out(f"아직 만들지 않은 명령입니다: {GROUP} {c}")
    return False
