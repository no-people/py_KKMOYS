"""명령 묶음 `io`(가져오기·내보내기). 담당: 기능 6.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from datetime import datetime
import os
from ..common import money
from ..common.cliutil import _period
from ..features import transfer_io

GROUP = 'io'


def _add_filter_args(parser, period_args):
    period_args(parser)
    parser.add_argument("--category", default=None, help="내보낼 지출 분류")


def _resolve_period(args):
    if getattr(args, "month", None) or getattr(args, "start", None) or getattr(args, "end", None):
        return _period(args)
    return None, None


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="가져오기·내보내기").add_subparsers(dest="cmd")

    p_csv = grp.add_parser("export-csv", help="지출을 CSV 파일로 내보내기")
    p_csv.add_argument("path", help="저장할 CSV 파일 경로")
    _add_filter_args(p_csv, period_args)

    p_json = grp.add_parser("export-json", help="지출을 JSON 파일로 내보내기")
    p_json.add_argument("path", help="저장할 JSON 파일 경로")
    _add_filter_args(p_json, period_args)

    p_ver = grp.add_parser("verify", help="내보낸 파일 합계 검증")
    p_ver.add_argument("path", help="검증할 CSV 또는 JSON 파일 경로")
    _add_filter_args(p_ver, period_args)

    p_bak = grp.add_parser("backup", help="전체 자료 백업")
    p_bak.add_argument("path", nargs="?", default=None, help="저장할 백업 파일 경로 (생략 시 backup_dir 에 자동 생성)")

    p_res = grp.add_parser("restore", help="백업 파일에서 전체 자료 복원")
    p_res.add_argument("path", help="복원할 백업 파일 경로")

    return grp


def run(c, args, cfg, store, out):
    if c == "export-csv":
        start, end = _resolve_period(args)
        count, total = transfer_io.export_csv(
            store, args.path, start=start, end=end, category=args.category
        )
        out(f"CSV 내보내기: {count}건, 합계 {money.fmt(total)}원 -> {args.path}")
        return False

    if c == "export-json":
        start, end = _resolve_period(args)
        count, total = transfer_io.export_json(
            store, args.path, start=start, end=end, category=args.category
        )
        out(f"JSON 내보내기: {count}건, 합계 {money.fmt(total)}원 -> {args.path}")
        return False

    if c == "verify":
        start, end = _resolve_period(args)
        ok, file_sum, record_sum = transfer_io.verify_export(
            store, args.path, start=start, end=end, category=args.category
        )
        status = "일치" if ok else "불일치"
        out(f"검증 {status}: 파일 {money.fmt(file_sum)}원 / 기록 {money.fmt(record_sum)}원")
        return False

    if c == "backup":
        target = args.path
        if not target:
            backup_dir = cfg.get("backup_dir") or os.path.join(os.path.dirname(os.path.abspath(store.path)), "backup")
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = os.path.join(backup_dir, f"full-backup-{stamp}.json")
        m_cnt, e_cnt = transfer_io.backup_all(store, target)
        out(f"전체 백업 완료: 회원 {m_cnt}명, 지출 {e_cnt}건 -> {target}")
        return False

    if c == "restore":
        m_cnt, e_cnt = transfer_io.restore_all(store, args.path)
        out(f"전체 복원 완료: 회원 {m_cnt}명, 지출 {e_cnt}건 <- {args.path}")
        return True

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
