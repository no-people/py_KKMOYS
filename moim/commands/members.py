"""명령 묶음 `member`(참여자 명부). 담당: 기능 1(add·leave·list), 팀 공동 작업 설정 파일(load).

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common.textfmt import pad, width
from ..features import expenses

GROUP = 'member'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="참여자 명부").add_subparsers(dest="cmd")
    s = grp.add_parser("add", help="명부에 추가")
    s.add_argument("name", help="이름")
    s.add_argument("joined", help="가입일 YYYY-MM-DD")
    s = grp.add_parser("leave", help="탈퇴일 적기(그날까지 회원)")
    s.add_argument("name", help="이름")
    s.add_argument("left", help="탈퇴일 YYYY-MM-DD")
    grp.add_parser("list", help="명부 보기")
    return grp


def run(c, args, cfg, store, out):
    if c == "add":
        m = expenses.add_member(store, args.name, args.joined)
        out(f"명부 추가: {m['name']} (가입일 {m['joined']})")
        return True
    if c == "leave":
        m = expenses.leave_member(store, args.name, args.left)
        out(f"탈퇴 기록: {m['name']} (탈퇴일 {m['left']}, 그날까지 회원)")
        return True
    if c == "list":
        rows = [(m["name"], m["joined"] or "", m["left"] or "-") for m in expenses.list_members(store)]
        if not rows:
            out("명부가 비어 있습니다")
            return False
        headers = ("이름", "가입일", "탈퇴일")
        ws = [max(width(r[i]) for r in rows + [headers]) for i in range(3)]
        for r in [headers] + rows:
            out("  ".join(pad(v, ws[i]) for i, v in enumerate(r)).rstrip())
        out(f"모두 {len(rows)}명")
        return False
    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
