"""기능 6. 가져오기·내보내기.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/ledger.py duplicates — 같은 날·같은 사람·같은 금액 지출 찾기(공용: 기능 1)
  - common/dates.py month_key — 날짜의 달 이름(공용: 기능 3)
  - common/queries.py period_total — 기간 합계(공용: 기능 3·5)
  - common/csvio.py detect_encoding, read_csv_rows — 인코딩 판별과 CSV 읽기(공용: 기능 5의 은행 거래내역 가져오기)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import csv
import copy
import json
import os
from ..common import dates, ledger, money  # noqa: F401
from ..common.csvio import detect_encoding, read_csv_rows  # noqa: F401
from ..common.queries import active_members, category_of, expenses_in  # noqa: F401

EXPORT_FIELDS = ("id", "date", "payer", "amount", "category", "members", "weights", "memo")


def _select_expenses(store, start=None, end=None, category=None):
    """조건(기간·분류)에 맞는 유효 지출 목록을 고른다. 논리 삭제는 제외한다."""
    if start is not None or end is not None:
        if start is None or end is None:
            raise ValueError("시작일과 끝일을 함께 지정해야 합니다")
        items = expenses_in(store, start, end)
    else:
        items = [copy.deepcopy(e) for e in store.data.get("expenses", []) if not e.get("deleted")]

    if category is not None:
        target = category.strip()
        if not target:
            raise ValueError("분류 이름은 비어 있을 수 없습니다")
        items = [e for e in items if category_of(e) == target]
    return items


def _format_weights(weights):
    if not weights:
        return ""
    return ",".join(f"{name}:{ratio}" for name, ratio in weights.items())


def export_csv(store, path, start=None, end=None, category=None):
    """CSV 로 내보낸다(엑셀에서 한글이 깨지지 않게 UTF-8 BOM). 돌려주는 값: (건수, 합계)"""
    items = _select_expenses(store, start=start, end=end, category=category)
    total = sum(money.to_won(e["amount"]) for e in items)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for e in items:
            writer.writerow({
                "id": e["id"],
                "date": dates.fmt(e["date"]),
                "payer": e["payer"],
                "amount": money.to_won(e["amount"]),
                "category": category_of(e),
                "members": ",".join(e.get("members", [])),
                "weights": _format_weights(e.get("weights")),
                "memo": e.get("memo", ""),
            })
    return len(items), total


def export_json(store, path, start=None, end=None, category=None):
    """JSON 으로 내보낸다. 돌려주는 값: (건수, 합계)"""
    items = _select_expenses(store, start=start, end=end, category=category)
    total = sum(money.to_won(e["amount"]) for e in items)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return len(items), total


def file_total(path):
    """내보낸 파일의 금액 합계와 건수."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    _, ext = os.path.splitext(path)
    if ext.lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            rows = data.get("expenses", [])
        elif isinstance(data, list):
            rows = data
        else:
            raise ValueError(f"지원하지 않는 JSON 형식입니다: {path}")
        valid = [r for r in rows if not r.get("deleted")]
        return sum(money.to_won(r["amount"]) for r in valid), len(valid)

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "amount" not in reader.fieldnames:
            raise ValueError(f"금액(amount) 열이 없습니다: {path}")
        rows = list(reader)
    return sum(money.to_won(r["amount"]) for r in rows), len(rows)


def verify_export(store, path, start=None, end=None, category=None):
    """내보낸 파일 합계가 원래 기록 합계와 같은가. 돌려주는 값: (같은가, 파일 합계, 기록 합계)"""
    items = _select_expenses(store, start=start, end=end, category=category)
    expected_total = sum(money.to_won(e["amount"]) for e in items)
    exported_total, _ = file_total(path)
    return exported_total == expected_total, exported_total, expected_total


def roundtrip_check(store, path, start=None, end=None, category=None):
    """내보낸 파일을 다시 읽어 원래 기록과 똑같은지 대조. 다른 번호 목록을 돌려준다(비어 있으면 같음)."""
    raise NotImplementedError("이 함수를 구현한다")


def import_csv(store, path, mapping=None, encoding=None, preview=False):
    """CSV 지출을 가져온다. 돌려주는 값: {"encoding", "added": [번호], "duplicates": [줄 번호], "errors": [(줄 번호, 오류)]}
    preview=True 면 실제로 넣지 않고 검사만 한다. 이때 added 에는 들어갈 줄 번호가 담긴다."""
    raise NotImplementedError("이 함수를 구현한다")


def _count_snapshot(data):
    members = data.get("members", [])
    expenses = [e for e in data.get("expenses", []) if not e.get("deleted")]
    return len(members), len(expenses)


def backup_all(store, path):
    """전체 모임 자료를 지정한 JSON 파일로 백업한다. 돌려주는 값: (회원 수, 유효 지출 수)"""
    snapshot = copy.deepcopy(store.data)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return _count_snapshot(snapshot)


def restore_all(store, path):
    """백업 JSON 파일에서 전체 모임 자료를 복원한다. 돌려주는 값: (회원 수, 유효 지출 수)"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"백업 파일이 없습니다: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"백업 파일 형식이 잘못되었습니다: {path} ({exc.lineno}번째 줄)") from exc

    if not isinstance(loaded, dict):
        raise ValueError(f"백업 파일 형식이 잘못되었습니다: {path}")
    if not isinstance(loaded.get("members"), list) or not isinstance(loaded.get("expenses"), list):
        raise ValueError(f"백업 파일에 회원 또는 지출 목록이 없습니다: {path}")

    if os.path.exists(store.path):
        store.save()

    restored = copy.deepcopy(loaded)
    store.data.clear()
    store.data.update(restored)
    return _count_snapshot(store.data)


def merge(store, other_path):
    """다른 모임 자료(백업 파일)의 회원·지출을 합친다. 지출 번호는 새로 매긴다. 돌려주는 값: 합친 지출 수"""
    raise NotImplementedError("이 함수를 구현한다")
