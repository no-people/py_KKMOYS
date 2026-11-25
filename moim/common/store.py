"""자료 파일 저장. 모든 기능이 이 한 곳의 자료(store.data)를 읽고 쓴다.

자료 구조(EMPTY)는 최소 항목만 들어 있다. 기능에 필요한 항목은 그 기능 담당자가 EMPTY 에 추가한다.
옛 자료 파일에 새 항목이 없으면 읽을 때 기본값으로 채운다.
save·backups·recover 는 팀 공동 작업 "자료 파일 손상 대응" 담당이 완성한다.
"""

import copy
import json
import os
import re
import stat
import tempfile
from datetime import datetime

EMPTY = {
    "members": [],      # {"name", "joined", "left"}
    "expenses": [],     # {"id", "date", "payer", "amount", "members", "weights", "category", "memo", "deleted", "recurring_id", "category_fixed"}
                        # weights: {참여자 전원의 이름: 1 이상 정수 비율} 또는 None(균등). 없는 옛 지출은 None 으로 본다. 기능 4
                        # deleted: 삭제 표시 bool. 없는 옛 지출은 False 로 본다. 기능 1
                        # recurring_id: 반복 지출(recurring)로 만든 지출이면 그 반복 지출의 id, 직접 넣은 지출은 None. 없는 옛 지출은 None 으로 본다. 기능 4
                        # category_fixed: 사람이 직접 정한 분류면 True(다시 분류할 때 건너뜀). 없는 옛 지출은 False 로 본다. 기능 2
    "next_id": 1,
    "locks": [],        # {"start", "end"} 정산 확정 기간(양 끝 포함). 기능 4
    "recurring": [],    # {"id", "day", "payer", "amount", "members", "memo", "category", "start", "made"} 반복 지출. 기능 4
                        # id: 반복 지출끼리 따로 1부터(가장 큰 id + 1). day: 1~31, 그달에 없으면 말일
                        # category: 만든 지출에 넘길 분류 또는 None(미분류). start: 첫 달 "YYYY-MM"
                        # made: 이미 만든 달 "YYYY-MM" 목록(다시 만들지 않음). 읽는 쪽은 "recurring": null 을 빈 목록으로 본다
    "history": [],      # {"id", "action", "before", "after", "at"} 지출 변경 이력. 기능 1
    "payments": [],     # {"date", "member", "amount", "memo", "source"} 회비 입금. source: manual 또는 bank. 기능 5
    "transfers": [],    # {"date", "from", "to", "amount"} 이미 보낸 송금(부분 정산). from 이 to 에게 amount 원. 기능 4
}

_BACKUP_NAME_RE = re.compile(r"^data-\d{8}-\d{6}-\d{6}\.json$")


class Store:
    def __init__(self, path, backup_dir=None, keep=10):
        if isinstance(keep, bool) or not isinstance(keep, int) or keep < 0:
            raise ValueError("keep은 0 이상의 정수여야 합니다")
        self.path = path
        self.backup_dir = backup_dir or os.path.join(os.path.dirname(os.path.abspath(path)), "backup")
        self.keep = keep
        self.data = copy.deepcopy(EMPTY)
        self.recovered_from = None

    def load(self):
        if not os.path.exists(self.path):
            self.data = copy.deepcopy(EMPTY)
            return self
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self._check_shape(data)
        self.data = data
        return self

    @staticmethod
    def _check_shape(data):
        """members·expenses 는 꼭 있어야 한다. 나중에 추가된 항목이 없는 옛 파일은 기본값으로 채운다."""
        if not isinstance(data, dict):
            raise ValueError("자료 파일 형식이 아닙니다")
        for key in ("members", "expenses"):
            if not isinstance(data.get(key), list):
                raise ValueError(f"자료 파일에 {key} 항목이 없습니다")
        for key, value in EMPTY.items():
            data.setdefault(key, copy.deepcopy(value))

    def save(self):
        """임시 파일에 쓰고 fsync한 뒤 백업·os.replace로 교체하고 초과 백업을 정리한다.

        기존 파일이 있으면 권한 모드를 유지하며, 기존 파일이 없을 때 새로 만든 파일은
        mkstemp 기본 권한(0o600)으로 남는다. keep == 0 이면 새 백업을 만들지 않고 기존 백업만 정리한다.
        """
        self._check_shape(self.data)

        target_dir = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(target_dir, exist_ok=True)

        tmp_path = None
        backup_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=target_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            has_existing = os.path.exists(self.path)
            existing_mode = None
            if has_existing:
                existing_mode = stat.S_IMODE(os.stat(self.path).st_mode)
                if self.keep > 0:
                    os.makedirs(self.backup_dir, exist_ok=True)
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                    backup_name = f"data-{stamp}.json"
                    backup_path = os.path.join(self.backup_dir, backup_name)
                    with open(self.path, "rb") as src, open(backup_path, "wb") as dst:
                        dst.write(src.read())
                        dst.flush()
                        os.fsync(dst.fileno())

            if existing_mode is not None:
                try:
                    os.chmod(tmp_path, existing_mode)
                except OSError:
                    pass

            os.replace(tmp_path, self.path)
            tmp_path = None
            backup_path = None

            if has_existing:
                try:
                    existing = self.backups()
                    if self.keep == 0:
                        for old_path in existing:
                            os.remove(old_path)
                    elif len(existing) > self.keep:
                        for old_path in existing[:-self.keep]:
                            os.remove(old_path)
                except OSError:
                    pass
        except BaseException:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except OSError:
                    pass
            raise

    def backups(self):
        """백업 파일 목록(오래된 것부터)."""
        if not os.path.isdir(self.backup_dir):
            return []
        matched = [
            os.path.join(self.backup_dir, name)
            for name in os.listdir(self.backup_dir)
            if _BACKUP_NAME_RE.fullmatch(name) and os.path.isfile(os.path.join(self.backup_dir, name))
        ]
        matched.sort(key=lambda p: os.path.basename(p))
        return matched

    def _next_broken_path(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_path = f"{self.path}.broken-{stamp}"
        if not os.path.exists(base_path):
            return base_path
        idx = 1
        while True:
            candidate = f"{base_path}-{idx}"
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def recover(self):
        """사용 가능한 정상 백업을 먼저 찾은 뒤 깨진 파일을 옆에 남기고 복구한다."""
        candidates = list(reversed(self.backups()))
        selected_backup = None
        selected_data = None

        for backup_path in candidates:
            try:
                with open(backup_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                self._check_shape(loaded)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                continue
            selected_backup = backup_path
            selected_data = loaded
            break

        if selected_backup is None or selected_data is None:
            raise ValueError("복구할 수 있는 정상 백업 파일이 없습니다")

        if os.path.exists(self.path):
            broken_path = self._next_broken_path()
            os.replace(self.path, broken_path)

        self.data = selected_data
        self.recovered_from = selected_backup
        return self

    def new_id(self):
        eid = self.data["next_id"]
        self.data["next_id"] += 1
        return eid

    def get_expense(self, eid):
        for e in self.data["expenses"]:
            if e["id"] == int(eid):
                return e
        raise ValueError(f"{eid}번 지출이 없습니다")

    def member(self, name):
        for m in self.data["members"]:
            if m["name"] == name:
                return m
        return None

    def record(self, action, eid, before, after):
        """지출 변경 이력을 history 에 추가한다. before·after 는 deepcopy 로 보관한다. 저장은 하지 않는다."""
        history = self.data.get("history")
        if history is None:   # 옛 파일의 "history": null 이나 키가 없는 경우
            self.data["history"] = []
        elif not isinstance(history, list):
            raise ValueError("자료 파일의 history 형식이 잘못되었습니다")
        self.data["history"].append({
            "id": eid,
            "action": action,
            "before": copy.deepcopy(before),
            "after": copy.deepcopy(after),
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
