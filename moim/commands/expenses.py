"""명령 묶음 `exp`(지출 입력·관리). 담당: 기능 1.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import dates, money
from ..common.cliutil import _members, _period, _weights
from ..common.queries import category_of
from ..common.textfmt import pad, width
from ..features import expenses

GROUP = 'exp'


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
    return grp


def _parse_weights(text):
    try:
        return _weights(text)
    except ValueError:
        raise ValueError(f'비율 형식이 잘못되었습니다(예: "김민수=2;이서연=1"): {text}') from None


def _show(key, value):
    """지출 항목 값을 화면에 보일 글자로 바꾼다."""
    if key == "amount":
        return f"{money.fmt(value)}원"
    if key == "members":
        return ";".join(value)
    if key == "weights":
        return ";".join(f"{n}={w}" for n, w in value.items()) if value else "없음(똑같이 나눔)"
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
    if c is None:
        out(f"하위 명령을 지정하십시오: {GROUP} add, list (도움말: python -m moim {GROUP} -h)")
        return False
    out(f"아직 만들지 않은 명령입니다: {GROUP} {c}")
    return False
