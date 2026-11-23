"""설정 파일. 팀 공동 작업 "설정 파일" 담당이 항목을 채운다.

지금은 모임 이름과 자료 파일 위치만 있다. 공고문의 설정 파일 항목(명부 파일 위치, 총무, 예산, 분류별 예산,
1인당 월 회비, 경보 비율, 분류 규칙 파일, 백업·로그 폴더)을 DEFAULT 에 더한다.
"""

import copy
import json
import os

DEFAULT = {
    "group": "우리 모임",
    "data": "data.json",
    "members_file": "members.csv",
    "rules": "rules.json",
    "backup_dir": "backups",
    "log_dir": "logs",
    "treasurer": "",
    "budget": {
        "monthly": 0,
        "by_category": {},
    },
    "dues": {
        "monthly": 0,
    },
    "warn_ratio": 0.8,
}
PATH_KEYS = ("data", "members_file", "rules", "backup_dir", "log_dir")  # 설정 파일이 있는 폴더 기준으로 바꿀 경로 항목


def load(path="config.json"):
    cfg = copy.deepcopy(DEFAULT)
    base = os.path.dirname(os.path.abspath(path))
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                loaded = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"설정 파일 형식이 잘못되었습니다: {path}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"설정 파일 형식이 잘못되었습니다: {path}")
        for k, v in loaded.items():
            if isinstance(cfg.get(k), dict) and isinstance(v, dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    for key in PATH_KEYS:
        val = cfg.get(key)
        if val and not os.path.isabs(val):
            cfg[key] = os.path.join(base, val)
    return cfg


def save_default(path="config.json"):
    if os.path.exists(path):
        raise FileExistsError(f"이미 있습니다: {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT, f, ensure_ascii=False, indent=2)
