"""명령 묶음 `settle`(정산). 담당: 기능 4.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import money, textfmt
from ..common.cliutil import _period
from ..features import settle

GROUP = 'settle'

HEADERS = ["이름", "낸 돈", "부담", "보낸 송금", "받은 송금", "잔액"]   # 스켈레톤 PDF 8절 정산 결과 화면과 같은 열


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="정산").add_subparsers(dest="cmd", required=True)
    balance = grp.add_parser("balance", help="기간의 사람별 낸 돈·부담·송금·잔액과 잔액 합계 검사")
    period_args(balance)
    return grp


def _table(headers, rows, numeric):
    """표 문자열. textfmt.table(규격 6-1, 기능 3)을 쓰고, 아직 구현 전이면 같은 모양으로 직접 그린다."""
    try:
        return textfmt.table(headers, rows, numeric=numeric)
    except NotImplementedError:
        pass
    cells = [[money.fmt(v) if type(v) is int else str(v) for v in row] for row in rows]
    widths = [max([textfmt.width(h)] + [textfmt.width(r[i]) for r in cells]) for i, h in enumerate(headers)]

    def line(row, align):
        return "  ".join(textfmt.pad(v, widths[i], right=align and i in numeric) for i, v in enumerate(row)).rstrip()

    return "\n".join([line(headers, False), "  ".join("-" * w for w in widths)] + [line(r, True) for r in cells])


def balance_lines(rows):
    """balances 결과를 화면 줄 목록으로. 마지막 줄은 잔액 합계 검사(규칙대로면 0)."""
    if not rows:
        return ["이 기간에 정산할 지출·송금이 없습니다"]
    body = [[name, r["paid"], r["owed"], r["sent"], r["received"], r["balance"]] for name, r in rows.items()]
    lines = _table(HEADERS, body, numeric={1, 2, 3, 4, 5}).split("\n")
    total = settle.balance_sum(rows)
    if total == 0:
        lines.append("잔액 합계: 0")
    else:
        lines.append(f"잔액 합계: {money.fmt(total)} (경고: 0이 아닙니다. 자료를 확인하십시오)")
    return lines


def run(c, args, cfg, store, out):
    if c == "balance":
        start, end = _period(args)
        for line in balance_lines(settle.balances(store, start, end)):
            out(line)
        return False
    raise ValueError(f"모르는 정산 명령입니다: {c}")
