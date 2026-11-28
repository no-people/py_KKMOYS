"""명령 묶음 `settle`(정산). 담당: 기능 4.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import money, textfmt
from ..common.cliutil import _members, _period
from ..features import settle

GROUP = 'settle'

HEADERS = ["이름", "낸 돈", "부담", "보낸 송금", "받은 송금", "잔액"]   # 스켈레톤 PDF 8절 정산 결과 화면과 같은 열


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="정산").add_subparsers(dest="cmd", required=True)
    balance = grp.add_parser("balance", help="기간의 사람별 낸 돈·부담·송금·잔액과 잔액 합계 검사")
    period_args(balance)
    transfers = grp.add_parser("transfers", help="잔액을 맞추는 송금 목록(횟수를 줄인 '누가 누구에게 얼마')")
    period_args(transfers)
    lock = grp.add_parser("lock", help="정산 확정(잔액 합이 0일 때만). 확정 기간의 지출은 추가·수정·삭제할 수 없다")
    period_args(lock)
    radd = grp.add_parser("recurring-add", help="반복 지출 등록(매달 같은 날. 그달에 없는 날은 말일)")
    radd.add_argument("day", type=int, help="매달 날짜 1~31")
    radd.add_argument("payer", help="낸 사람")
    radd.add_argument("amount", help="금액(원). 쉼표 가능")
    radd.add_argument("members", help='참여자. 예: "김민수;이서연"')
    radd.add_argument("--memo", default="", help="메모")
    radd.add_argument("--start", required=True, help="이 달부터 만든다 YYYY-MM")
    rrun = grp.add_parser("recurring-run", help="이 날짜까지 아직 만들지 않은 반복 지출을 지출로 만든다")
    rrun.add_argument("--until", required=True, help="YYYY-MM-DD (이날까지 포함)")
    return grp


def balance_lines(rows):
    """balances 결과를 화면 줄 목록으로. 마지막 줄은 잔액 합계 검사(규칙대로면 0)."""
    if not rows:
        return ["이 기간에 정산할 지출·송금이 없습니다"]
    body = [[name, r["paid"], r["owed"], r["sent"], r["received"], r["balance"]] for name, r in rows.items()]
    lines = textfmt.table(HEADERS, body, numeric={1, 2, 3, 4, 5}).split("\n")   # 규격 6-1 (기능 3)
    total = settle.balance_sum(rows)
    if total == 0:
        lines.append("잔액 합계: 0")
    else:
        lines.append(f"잔액 합계: {money.fmt(total)} (경고: 0이 아닙니다. 자료를 확인하십시오)")
    return lines


def transfers_lines(transfers):
    """minimal_transfers 결과를 화면 줄 목록으로. 스켈레톤 PDF 8절 송금 목록 화면과 같은 모양."""
    if not transfers:
        return ["보낼 송금이 없습니다"]
    return [f"{frm} -> {to} {money.fmt(won)}원" for frm, to, won in transfers]


def _memo(text):
    return f" {text}" if text else ""


def recurring_lines(created, skipped):
    """run_recurring_report 결과를 화면 줄 목록으로."""
    lines = [f"반복 지출 만듦 {e['id']}번: {e['date']} {e['payer']} {money.fmt(e['amount'])}원 "
             f"({len(e['members'])}명){_memo(e['memo'])} (반복 {e['recurring_id']}번)" for e in created]
    lines += [f"건너뜀: 반복 {rid}번 {month} ({reason})" for rid, month, reason in skipped]
    lines.append(f"반복 지출 {len(created)}건을 만들었습니다" if created else "새로 만들 반복 지출이 없습니다")
    return lines


def run(c, args, cfg, store, out):
    if c == "balance":
        start, end = _period(args)
        for line in balance_lines(settle.balances(store, start, end)):
            out(line)
        return False
    if c == "transfers":
        start, end = _period(args)
        for line in transfers_lines(settle.minimal_transfers(settle.balances(store, start, end))):
            out(line)
        return False
    if c == "lock":
        start, end = _period(args)
        before = len(store.data.get("locks") or [])
        lock = settle.lock_period(store, start, end)
        if len(store.data.get("locks") or []) == before:   # 같은 기간이 이미 확정돼 있음 → 바뀐 것 없음
            out(f"이미 확정된 기간입니다: {lock['start']} ~ {lock['end']}")
            return False
        out(f"정산 확정: {lock['start']} ~ {lock['end']} (이 기간의 지출은 추가·수정·삭제·되살리기를 할 수 없고, 다른 날짜의 지출을 이 기간으로 옮길 수도 없습니다)")
        return True
    if c == "recurring-add":
        r = settle.add_recurring(store, args.day, args.payer, args.amount, _members(args.members), args.memo, args.start)
        out(f"반복 지출 등록 {r['id']}번: 매달 {r['day']}일 {r['payer']} {money.fmt(r['amount'])}원 "
            f"({len(r['members'])}명){_memo(r['memo'])}, {r['start']}부터 (그달에 없는 날은 말일, settle recurring-run 으로 만듦)")
        return True
    if c == "recurring-run":
        created, skipped = settle.run_recurring_report(store, args.until)
        for line in recurring_lines(created, skipped):
            out(line)
        return bool(created)
    raise ValueError(f"모르는 정산 명령입니다: {c}")
