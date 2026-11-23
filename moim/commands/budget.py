"""명령 묶음 `budget`(예산·회비). 담당: 기능 5.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import money, textfmt
from ..features import budget

GROUP = 'budget'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="예산·회비").add_subparsers(dest="cmd", required=True)
    status = grp.add_parser("status", help="설정된 월 예산·사용액·남은 금액")
    status.add_argument("--month", required=True, help="YYYY-MM")
    status.add_argument("--today", help="이 날짜까지의 지출만 조회(YYYY-MM-DD)")
    categories = grp.add_parser("categories", help="분류별 예산·사용액·초과 경보")
    categories.add_argument("--month", required=True, help="YYYY-MM")
    table = grp.add_parser("table", help="분류별 예산 대비 실제 지출 표")
    table.add_argument("--month", required=True, help="YYYY-MM")
    pay = grp.add_parser("pay", help="회비 입금 기록")
    pay.add_argument("--date", required=True, help="YYYY-MM-DD")
    pay.add_argument("--member", required=True, help="명부에 있는 회원 이름")
    pay.add_argument("--amount", required=True, help="입금액(원)")
    pay.add_argument("--memo", default="", help="입금 메모")
    balance = grp.add_parser("balance", help="회비 입금 합계에서 지출을 뺀 통장 잔고")
    balance.add_argument("--until", help="이 날짜까지 조회(YYYY-MM-DD, 당일 포함)")
    bank = grp.add_parser("import-bank", help="은행 CSV에서 지출·회비 가져오기")
    bank.add_argument("path", help="은행 거래내역 CSV 파일")
    bank.add_argument("--treasurer", help="출금을 기록할 총무 이름(기본값: 설정 파일)")
    unpaid = grp.add_parser("unpaid", help="그달 1일 또는 말일 회원의 회비 미납 목록")
    unpaid.add_argument("--month", required=True, help="YYYY-MM")
    return grp


def run(c, args, cfg, store, out):
    if c == "status":
        status = budget.month_status(store, cfg, args.month, args.today)
        out(f"{args.month} 월 예산: {money.fmt(status['budget'])}원")
        out(f"사용액: {money.fmt(status['spent'])}원")
        out(f"남은 금액: {money.fmt(status['remaining'])}원")
        out("예산 초과" if status["over"] else
            "예산 주의: 경보 기준 초과" if status["warn"] else "예산 이내")
        return False
    if c == "categories":
        statuses = budget.category_status(store, cfg, args.month)
        for name, item in statuses.items():
            label = "초과" if item["over"] else "주의" if item["warn"] else "이내"
            out(f"{name}: 예산 {money.fmt(item['budget'])}원, "
                f"사용 {money.fmt(item['spent'])}원, "
                f"잔액 {money.fmt(item['remaining'])}원 ({label})")
        if not statuses:
            out("분류별 예산과 지출이 없습니다.")
        return False
    if c == "pay":
        payment = budget.record_payment(store, args.date, args.member, args.amount, args.memo)
        out(f"회비 입금 기록: {payment['date']} {payment['member']} "
            f"{money.fmt(payment['amount'])}원")
        return True
    if c == "table":
        rows = budget.budget_table(store, cfg, args.month)
        out(textfmt.table(["분류", "예산", "실제", "차이"], rows[:-1],
                          total=rows[-1], numeric={1, 2, 3}))
        if sum(row[1] for row in rows[:-1]) != rows[-1][1]:
            out("전체 예산은 월 전체 예산 설정 기준입니다.")
        return False
    if c == "balance":
        balance = budget.treasury_balance(store, args.until)
        out(f"통장 잔고: {money.fmt(balance)}원")
        return False
    if c == "import-bank":
        result = budget.import_bank(store, args.path, args.treasurer or cfg.get("treasurer"))
        out(f"은행 가져오기: 지출 {len(result['expenses'])}건, 회비 입금 {result['payments']}건")
        if result["duplicates"]:
            out("중복으로 건너뛴 행: " + ", ".join(map(str, result["duplicates"])))
        for line, error in result["errors"]:
            out(f"오류 {line}행: {error}")
        return bool(result["expenses"] or result["payments"])
    if c == "unpaid":
        rows = budget.unpaid(store, cfg, args.month)
        for name, paid, missing in rows:
            out(f"{name}: 납부 {money.fmt(paid)}원, 미납 {money.fmt(missing)}원")
        if not rows:
            out("미납자가 없습니다.")
        return False
    raise ValueError(f"모르는 예산·회비 명령입니다: {c}")
