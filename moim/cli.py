"""통합 실행 틀(최소판). 팀 공동 작업 "통합 실행" 담당이 완성한다.

지금 하는 일: 명령 묶음(moim/commands/*.py)을 붙이고, 설정을 읽고, 자료를 읽어 실행한 뒤 바뀌었으면 저장한다.
오류(ValueError·파일 오류·미구현)는 "오류: 이유" 한 줄로 표준 오류에 안내하고 종료 코드 1 을 돌려준다.
`init` 은 기본 설정 파일(--config 경로)을 만든다. 설정·자료 파일을 읽지 않는다.
로그(설정의 log_dir/YYYY-MM-DD.log): 자료를 바꾼 명령은 저장한 뒤 화면에 낸 줄을 INFO 로, 설정을 읽은 뒤 난 오류는 ERROR 로 남긴다.
조회만 한 명령은 남기지 않는다. 로그를 못 남겨도 명령 결과는 그대로 두고 경고만 한다.
더할 일: 자료 파일이 깨졌을 때 복구 안내.
"""

import argparse
import json
import logging
import os
import sys

from .commands import budget, categorize, expenses, members, report, settle, transfer_io
from .common import config as cfgmod
from .common import log
from .common.store import Store

COMMANDS = [members, expenses, categorize, report, settle, budget, transfer_io]
INIT = "init"
INIT_FILL = "treasurer(총무), budget.monthly(월 예산), dues.monthly(월 회비)"   # 기본값이 비어 있어 채워야 쓰는 항목


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
    """설정·자료 파일을 읽는다. JSON 이 깨졌거나 UTF-8 이 아니면 어느 파일인지 담은 ValueError."""
    try:
        return loader(path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{what} 형식이 잘못되었습니다: {path} ({exc.lineno}번째 줄)") from None
    except UnicodeDecodeError:
        raise ValueError(f"{what}의 글자 인코딩을 읽을 수 없습니다(UTF-8 이어야 합니다): {path}") from None


def period_args(sp):
    sp.add_argument("--month", help="YYYY-MM")
    sp.add_argument("--start", help="YYYY-MM-DD")
    sp.add_argument("--end", help="YYYY-MM-DD")


def build_parser():
    p = ArgParser(prog="moim", description="모임 회비·지출 정산 도구")
    p.add_argument("--config", default="config.json", help="설정 파일 경로")
    sub = p.add_subparsers(dest="group", required=True)
    sub.add_parser(INIT, help="기본 설정 파일 만들기(이미 있으면 거부). 경로: python -m moim --config <경로> init")
    for mod in COMMANDS:
        mod.add_parser(sub, period_args)
    return p


def run(args, cfg, store, out=print):
    for mod in COMMANDS:
        if mod.GROUP == args.group:
            return mod.run(getattr(args, "cmd", None), args, cfg, store, out)
    raise ValueError(f"모르는 명령입니다: {args.group}")


def init(path, out=print):
    """기본 설정 파일을 만들고 다음에 할 일을 안내한다. 이미 있으면 덮어쓰지 않는다(config.save_default)."""
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        raise ValueError(f"설정 파일을 만들 폴더가 없습니다: {folder}")
    cfgmod.save_default(path)
    out(f"설정 파일을 만들었습니다: {path}")
    out(f"모임에 맞게 채울 항목: {INIT_FILL}")
    out("자료 파일(data)은 처음 자료를 저장할 때 만들어집니다")


def command_name(args):
    """로그에 적을 명령 이름. 예: "exp add", "settle balance"."""
    return " ".join(x for x in (args.group, getattr(args, "cmd", None)) if x)


def _raise_write_error(record):
    """logging 은 쓰기 오류를 handleError 로 삼키고 트레이스백을 찍는다. 대신 그 오류를 그대로 올린다."""
    raise   # emit 의 except 안에서 불리므로 처리 중인 오류가 다시 올라간다


def write_log(cfg, level, lines, warn=True):
    """cfg["log_dir"] 의 오늘 로그 파일에 줄들을 남긴다. 실패해도 명령 결과(종료 코드)는 바꾸지 않는다.

    폴더·파일 열기와 쓰기 실패 모두 warn 이면 "경고: 로그를 남기지 못했습니다: 이유" 한 줄, 아니면 아무것도 내지 않는다
    (명령 오류 때는 "오류: 이유" 한 줄만 보이게).
    """
    handlers = []
    try:
        logger = log.get_logger(cfg["log_dir"])
        handlers = list(logger.handlers)
        for h in handlers:
            h.handleError = _raise_write_error
        for line in lines:
            logger.log(level, " ".join(str(line).split()))   # 여러 줄(표)도 한 줄로
    except (OSError, ValueError) as exc:   # ValueError: 닫힌 파일에 쓰기 등
        if warn:
            print(f"경고: 로그를 남기지 못했습니다: {error_reason(exc)}", file=sys.stderr)
    finally:
        for h in handlers:
            h.__dict__.pop("handleError", None)   # 다음 사용을 위해 원래 handleError 로 되돌림


def main(argv=None, out=print):
    """실행 결과 종료 코드: 성공 0, 오류 1. 오류는 표준 오류에 "오류: 이유" 한 줄로 알리고 저장하지 않는다."""
    cfg, shown = None, []

    def show(line):
        shown.append(line)
        out(line)

    try:
        args = build_parser().parse_args(argv)
        if args.group == INIT:
            init(args.config, out)
            return 0
        cfg = load_json_file(cfgmod.load, args.config, "설정 파일")
        store = load_json_file(lambda p: Store(p).load(), cfg["data"], "자료 파일")
        changed = run(args, cfg, store, show)
        if changed:
            store.save()
    except (ValueError, OSError, NotImplementedError) as exc:
        reason = error_reason(exc)
        print(f"오류: {reason}", file=sys.stderr)
        if cfg is not None:   # 설정을 못 읽었으면 로그 폴더도 모른다
            write_log(cfg, logging.ERROR, [f"{command_name(args)} 실패: {reason}"], warn=False)
        return 1
    if changed:   # 저장이 끝난 뒤에만: 저장 안 된 변경이 로그에만 남지 않게
        write_log(cfg, logging.INFO, shown or [f"{command_name(args)} 저장"])
    return 0
