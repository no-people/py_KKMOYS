"""명령 묶음 `report`(월별·기간 보고서). 담당: 기능 3.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import money, textfmt
from ..features import report as report_feat

GROUP = 'report'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="보고서").add_subparsers(dest="cmd")
    s_search = grp.add_parser("search", help="지출 검색")
    period_args(s_search)
    s_search.add_argument("--person", default=None, help="낸 사람 또는 참여자 이름")
    s_search.add_argument("--min", dest="min_amount", default=None, help="최소 금액")
    s_search.add_argument("--max", dest="max_amount", default=None, help="최대 금액")
    s_search.add_argument("--word", default=None, help="메모에 포함된 낱말")
    return grp


def run(c, args, cfg, store, out):
    if c == "search":
        start, end = args.start, args.end
        if getattr(args, "month", None):
            start, end = report_feat._month_bounds(report_feat._to_ym_tuple(args.month))

        rows_data = report_feat.search(
            store,
            start=start,
            end=end,
            person=args.person,
            min_amount=args.min_amount,
            max_amount=args.max_amount,
            word=args.word,
        )
        if not rows_data:
            out("검색 결과가 없습니다.")
            return False

        rows = [
            [e.get("id", ""), e["date"], e.get("payer", ""), e["amount"], e.get("memo", "")]
            for e in rows_data
        ]
        total_amt = sum(e["amount"] for e in rows_data)
        out(textfmt.table(
            ["번호", "날짜", "낸 사람", "금액", "메모"],
            rows,
            total=["합계", "", "", total_amt, f"{len(rows_data)}건"],
            numeric={0, 3},
        ))
        return False
    return False
