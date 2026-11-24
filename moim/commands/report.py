"""명령 묶음 `report`(월별·기간 보고서). 담당: 기능 3.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import money
from ..features import report as report_feat

GROUP = 'report'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="보고서").add_subparsers(dest="cmd")
    s_mom = grp.add_parser("mom", help="전월 대비 증감과 증감률")
    s_mom.add_argument("--month", required=True, help="기준 월 (YYYY-MM)")
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

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
