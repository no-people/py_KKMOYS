"""명령 묶음 `report`(월별·기간 보고서). 담당: 기능 3.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import dates, money, textfmt
from ..common.cliutil import _period
from ..features import report as report_feat

GROUP = 'report'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="보고서").add_subparsers(dest="cmd")
    s_mom = grp.add_parser("mom", help="전월 대비 증감과 증감률")
    s_mom.add_argument("--month", required=True, help="기준 월 (YYYY-MM)")

    s_search = grp.add_parser("search", help="지출 검색")
    period_args(s_search)
    s_search.add_argument("--person", default=None, help="낸 사람 또는 참여자 이름")
    s_search.add_argument("--min", dest="min_amount", default=None, help="최소 금액")
    s_search.add_argument("--max", dest="max_amount", default=None, help="최대 금액")
    s_search.add_argument("--word", default=None, help="메모에 포함된 낱말")

    s_cat = grp.add_parser("category", help="분류별 건수·금액 표와 막대그래프")
    period_args(s_cat)
    s_mon = grp.add_parser("monthly", help="월별 지출 합계 표와 막대그래프")
    s_mon.add_argument("--from", dest="first", required=True, help="시작 월 (YYYY-MM)")
    s_mon.add_argument("--to", dest="last", required=True, help="끝 월 (YYYY-MM)")

    s_month = grp.add_parser("month", help="월간 보고서")
    s_month.add_argument("--month", required=True, help="기준 월 (YYYY-MM)")
    return grp


def run(c, args, cfg, store, out):
    if c == "mom":
        cur, prev, diff, rate = report_feat.month_over_month(store, args.month)
        sign = "+" if diff > 0 else ""
        out(f"[{args.month} 전월 대비]")
        out(f"지난달: {money.fmt(prev)}원")
        out(f"이번 달: {money.fmt(cur)}원")
        out(f"증감: {sign}{money.fmt(diff)}원")
        if rate is None:
            out("증감률: 지난달 지출이 0원이어서 계산할 수 없습니다.")
        else:
            out(f"증감률: {sign}{rate:.1f}%")
        return False

    if c == "search":
        start, end = args.start, args.end
        if getattr(args, "month", None):
            start, end = dates.month_range(*dates.parse_month(args.month))

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

        amounts = [money.to_won(e.get("amount", 0)) for e in rows_data]
        rows = [
            [
                e.get("id", ""),
                e.get("date", ""),
                e.get("payer", ""),
                amt,
                e.get("memo") or "",
            ]
            for e, amt in zip(rows_data, amounts)
        ]
        total_amt = sum(amounts)
        out(
            textfmt.table(
                ["번호", "날짜", "낸 사람", "금액", "메모"],
                rows,
                total=["합계", "", "", total_amt, f"{len(rows_data)} 건"],
                numeric={0, 3},
            )
        )
        return False

    if c == "category":
        start, end = _period(args)
        if dates.parse(start) > dates.parse(end):
            raise ValueError("시작일이 끝일보다 늦을 수 없습니다.")
        out(report_feat.category_table(store, start, end))
        return False

    if c == "monthly":
        out(report_feat.monthly_table(store, args.first, args.last))
        return False 

    if c == "month":
        out(report_feat.month_report(store, args.month).rstrip("\n"))
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
