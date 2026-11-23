"""명령 묶음 `report`(월별·기간 보고서). 담당: 기능 3.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from moim.common import cliutil
from moim.features import report as report_feature

GROUP = "report"


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="보고서").add_subparsers(dest="cmd")

    p_month = grp.add_parser("month", help="월간 보고서")
    p_month.add_argument("--month", default=None, help="대상 월 (YYYY-MM)")
    p_month.add_argument("--out", dest="out_path", default=None, help="저장할 .txt 파일 경로")

    p_summary = grp.add_parser("summary", help="기간 요약")
    period_args(p_summary)

    p_months = grp.add_parser("months", help="월별 합계 추이")
    p_months.add_argument("--start", required=True, help="시작 월 (YYYY-MM)")
    p_months.add_argument("--end", required=True, help="종료 월 (YYYY-MM)")

    p_mom = grp.add_parser("mom", help="전월 대비 증감")
    p_mom.add_argument("--month", required=True, help="대상 월 (YYYY-MM)")

    p_top = grp.add_parser("top", help="상위 지출")
    period_args(p_top)
    p_top.add_argument("--limit", type=int, default=5, help="조회 건수")

    p_big = grp.add_parser("biggest-day", help="최대 지출일")
    period_args(p_big)

    p_search = grp.add_parser("search", help="지출 검색")
    period_args(p_search)
    p_search.add_argument("--payer", default=None, help="낸 사람")
    p_search.add_argument("--min-amount", default=None, help="최소 금액")
    p_search.add_argument("--max-amount", default=None, help="최대 금액")
    p_search.add_argument("--keyword", default=None, help="검색어")

    return grp


def _resolve_period(args, store=None):
    if hasattr(cliutil, "_period"):
        return cliutil._period(args)
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    return start, end


def run(c, args, cfg, store, out):
    if c == "month":
        ym = getattr(args, "month", None) or "2026-11"
        out_path = getattr(args, "out_path", None)
        if out_path:
            saved = report_feature.save_report(store, ym, out_path)
            out(f"보고서 저장 완료: {saved}")
        else:
            out(report_feature.month_report(store, ym))
        return False

    if c == "summary":
        start, end = _resolve_period(args, store)
        s = report_feature.period_summary(store, start, end)
        out(
            f"합계: {s['total']}원 | 분류 {len(s['by_category'])}개 | 인원 {len(s['by_person'])}명"
        )
        return False

    if c == "months":
        rows = report_feature.monthly_totals(store, args.start, args.end)
        out("\n".join(f"{ym}: {amt}" for ym, amt in rows))
        return False

    if c == "mom":
        info = report_feature.month_over_month(store, args.month)
        out(
            f"{info['month']} ({info['total']}) vs {info['prev_month']} ({info['prev_total']}): "
            f"차이 {info['diff']}"
        )
        return False

    if c == "top":
        start, end = _resolve_period(args, store)
        items = report_feature.top_expenses(store, start, end, limit=args.limit)
        out(
            "\n".join(
                f"#{e.get('id')} {e.get('date')} {e.get('payer')} {e.get('amount')} {e.get('memo', '')}".rstrip()
                for e in items
            )
        )
        return False

    if c == "biggest-day":
        start, end = _resolve_period(args, store)
        best = report_feature.biggest_day(store, start, end)
        out(f"{best[0]}: {best[1]}" if best else "지출 없음")
        return False

    if c == "search":
        start, end = _resolve_period(args, store)
        items = report_feature.search(
            store,
            start=start,
            end=end,
            payer=getattr(args, "payer", None),
            min_amount=getattr(args, "min_amount", None),
            max_amount=getattr(args, "max_amount", None),
            keyword=getattr(args, "keyword", None),
        )
        out(
            "\n".join(
                f"#{e.get('id')} {e.get('date')} {e.get('payer')} {e.get('amount')} {e.get('memo', '')}".rstrip()
                for e in items
            )
        )
        return False

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False