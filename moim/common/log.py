"""로그. 팀 공동 작업 "로그" 담당이 날짜별 파일(logs/YYYY-MM-DD.log)에 남기도록 완성한다."""

import logging
import os
from datetime import date

LOGGER_NAME = "moim"
FORMAT = "%(asctime)s %(levelname)s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"
_MARK = "_moim_file_handler"  # 이 모듈이 단 핸들러 표시


def get_logger(log_dir):
    """log_dir/YYYY-MM-DD.log 에 UTF-8 로 덧붙여 쓰는 "moim" 로거를 돌려준다.

    한 줄 형식: "2026-11-16 17:32:15 INFO 지출 추가 1번 36,000원".
    여러 번 불러도 핸들러는 하나다. 같은 파일이면 그대로 두고, 다른 폴더(또는 날짜)면 바꿔 단다.
    log_dir 폴더가 없으면 만든다.
    """
    log_dir = os.fspath(log_dir)
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.abspath(os.path.join(log_dir, date.today().isoformat() + ".log"))

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 화면(stderr)에 섞이지 않게 파일에만 쓴다

    for h in list(logger.handlers):
        if getattr(h, _MARK, False) and h.baseFilename == path:
            return logger
        if getattr(h, _MARK, False) or isinstance(h, logging.NullHandler):
            logger.removeHandler(h)
            h.close()

    handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter(FORMAT, DATEFMT))
    setattr(handler, _MARK, True)
    logger.addHandler(handler)
    return logger
