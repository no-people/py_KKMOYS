"""명령 묶음 `io`(가져오기·내보내기). 담당: 기능 6.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

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


def _parse_mapping(raw_map):
    if not raw_map:
        return None
    mapping = {}
    for pair in raw_map.split(","):
        token = pair.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"열 연결 형식이 잘못되었습니다(원본열=필드명): {token}")
        src, dst = token.split("=", 1)
        src, dst = src.strip(), dst.strip()
        if not src or not dst:
            raise ValueError(f"열 연결 형식이 잘못되었습니다: {token}")
        mapping[src] = dst
    return mapping or None


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

    p_imp = grp.add_parser("import-csv", help="CSV 파일에서 지출 가져오기")
    p_imp.add_argument("path", help="가져올 CSV 파일 경로")
    p_imp.add_argument("--map", dest="mapping", default=None, help="열 이름 연결 (예: 지출일=date,결제자=payer,금액=amount)")
    p_imp.add_argument("--encoding", default=None, help="파일 글자 인코딩 (utf-8-sig 또는 cp949)")
    p_imp.add_argument("--preview", action="store_true", help="실제로 넣지 않고 미리 보기만 실행")

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

    if c == "import-csv":
        mapping = _parse_mapping(args.mapping)
        res = transfer_io.import_csv(
            store,
            args.path,
            mapping=mapping,
            encoding=args.encoding,
            preview=args.preview,
        )
        prefix = "(미리 보기) " if args.preview else ""
        out(
            f"{prefix}CSV 가져오기({res['encoding']}): "
            f"추가 {len(res['added'])}건, 중복 {len(res['duplicates'])}건, 오류 {len(res['errors'])}건"
        )
        if res["duplicates"]:
            out(f"중복 줄 번호: {', '.join(str(n) for n in res['duplicates'])}")
        for lineno, msg in res["errors"]:
            out(f"{lineno}번째 줄 오류: {msg}")
        return (not args.preview) and bool(res["added"])

    out(f"아직 만들지 않은 명령입니다: {GROUP} {c or ''}".rstrip())
    return False
