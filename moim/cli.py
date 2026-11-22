"""통합 실행 틀(최소판). 팀 공동 작업 "통합 실행" 담당이 완성한다.

지금 하는 일: 명령 묶음(moim/commands/*.py)을 붙이고, 설정을 읽고, 자료를 읽어 실행한 뒤 바뀌었으면 저장한다.
오류(ValueError·파일 오류·미구현)는 "오류: 이유" 한 줄로 표준 오류에 안내하고 종료 코드 1 을 돌려준다.
더할 일: init(기본 설정 파일 만들기), 로그 남기기, 자료 파일이 깨졌을 때 복구 안내.
"""

import argparse
import json
import sys

from .commands import budget, categorize, expenses, members, report, settle, transfer_io
from .common import config as cfgmod
from .common.store import Store

COMMANDS = [members, expenses, categorize, report, settle, budget, transfer_io]


class UsageError(ValueError):
    """명령행 인자가 잘못됨. argparse 의 사용법 출력·종료 코드 2 대신 "오류: 이유" 로 안내한다."""


class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(f"명령 형식이 잘못되었습니다: {message} (도움말: python -m moim -h)")


def error_reason(exc):
    """예외를 사용자에게 보일 한 줄 이유로 바꾼다."""
    name = getattr(exc, "filename", None)
    if isinstance(exc, FileNotFoundError) and name:
        reason = f"파일이 없습니다: {name}"
    elif isinstance(exc, PermissionError) and name:
        reason = f"파일에 접근할 권한이 없습니다: {name}"
    elif isinstance(exc, IsADirectoryError) and name:
        reason = f"파일이 아니라 폴더입니다: {name}"
    elif isinstance(exc, OSError) and name:
        reason = f"파일을 읽거나 쓸 수 없습니다: {name} ({exc.strerror})"
    elif isinstance(exc, UnicodeError):
        reason = "파일의 글자 인코딩을 읽을 수 없습니다(UTF-8 이어야 합니다)"
    elif isinstance(exc, NotImplementedError):
        reason = "아직 구현되지 않은 기능입니다" + (f": {exc}" if str(exc) else "")
    else:
        reason = str(exc) or type(exc).__name__
    return " ".join(reason.split())   # 여러 줄 메시지도 한 줄로


def load_json_file(loader, path, what):
    """설정·자료 파일을 읽는다. JSON 이 깨졌으면 어느 파일 몇째 줄인지 담은 ValueError."""
    try:
        return loader(path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{what} 형식이 잘못되었습니다: {path} ({exc.lineno}번째 줄)") from None


def period_args(sp):
    sp.add_argument("--month", help="YYYY-MM")
    sp.add_argument("--start", help="YYYY-MM-DD")
    sp.add_argument("--end", help="YYYY-MM-DD")


def build_parser():
    p = ArgParser(prog="moim", description="모임 회비·지출 정산 도구")
    p.add_argument("--config", default="config.json", help="설정 파일 경로")
    sub = p.add_subparsers(dest="group", required=True)
    for mod in COMMANDS:
        mod.add_parser(sub, period_args)
    return p


def run(args, cfg, store, out=print):
    for mod in COMMANDS:
        if mod.GROUP == args.group:
            return mod.run(getattr(args, "cmd", None), args, cfg, store, out)
    raise ValueError(f"모르는 명령입니다: {args.group}")


def main(argv=None, out=print):
    """실행 결과 종료 코드: 성공 0, 오류 1. 오류는 표준 오류에 "오류: 이유" 한 줄로 알리고 저장하지 않는다."""
    try:
        args = build_parser().parse_args(argv)
        cfg = load_json_file(cfgmod.load, args.config, "설정 파일")
        store = load_json_file(lambda p: Store(p).load(), cfg["data"], "자료 파일")
        if run(args, cfg, store, out):
            store.save()
    except (ValueError, OSError, NotImplementedError) as exc:
        print(f"오류: {error_reason(exc)}", file=sys.stderr)
        return 1
    return 0
