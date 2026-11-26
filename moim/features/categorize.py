"""기능 2. 분류 규칙.

이 기능을 구현하려면 아래 공통 함수를 이 기능 담당자가 채운다(공통 모듈 병합 요청으로).
  - common/queries.py category_of — 지출의 분류 이름(공용: 기능 3·5·6)
  - common/queries.py category_totals — 분류별 건수·금액(공용: 기능 3·5)

이 기능에 필요한 자료 항목은 common/store.py 의 EMPTY 에 이 기능 담당자가 추가한다.
  - 직접 정한 분류의 고정 표시(category_fixed)

아래 함수의 이름과 인자는 바꾸지 않는다(인수 테스트와 채점이 이 이름으로 실행된다).
필요하면 함수를 더 만들어도 된다. 다른 기능 파일은 불러 쓰지 않는다.
"""

import json
import os
import tempfile
from ..common import money
from ..common.queries import category_of, category_totals, is_locked
from ..common.rules import UNCATEGORIZED


def load_rules(path):
    """규칙 파일(JSON)을 읽는다. 파일이 없으면 빈 목록, 형식이 잘못되면 ValueError."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rules = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"규칙 파일 형식이 잘못되었습니다: {path}") from exc
    # 목록이고, 규칙마다 분류 이름(문자열)이 있어야 한다
    if not isinstance(rules, list):
        raise ValueError(f"규칙 파일 형식이 잘못되었습니다: {path}")
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict) or not isinstance(rule.get("category"), str):
            raise ValueError(f"규칙 파일의 {i}번 규칙 형식이 잘못되었습니다")
    return rules


def save_rules(path, rules):
    """규칙 목록을 JSON 으로 저장한다. 임시 파일에 다 쓴 뒤 바꿔치기해서 도중에 멈춰도 원래 파일이 남는다."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        os.remove(tmp)
        raise


def add_rule(rules, category, keywords=None, priority=0, payer=None, min_amount=None, max_amount=None):
    """규칙을 목록 끝에 추가하고, 추가한 규칙을 돌려준다(먼저 등록한 규칙이 앞)."""
    # 분류 이름은 앞뒤 공백을 떼고 넣는다(category_of 와 같은 이름이 되게)
    if not isinstance(category, str) or not category.strip():
        raise ValueError("분류 이름을 입력하세요")
    if isinstance(keywords, str):   # 키워드 하나만 문자열로 줘도 받는다
        keywords = [keywords]
    keywords = [k.strip() for k in (keywords or []) if k.strip()]
    rule = {"category": category.strip(), "keywords": keywords, "priority": int(priority),
            "payer": payer,
            "min_amount": money.to_won(min_amount) if min_amount is not None else None,
            "max_amount": money.to_won(max_amount) if max_amount is not None else None}
    # 조건이 하나도 없는 규칙은 모든 지출에 맞아 버리므로 거부
    if not keywords and payer is None and min_amount is None and max_amount is None:
        raise ValueError("키워드·낸 사람·금액 범위 가운데 조건을 하나 이상 주세요")
    rules.append(rule)
    return rule


def remove_rule(rules, index):
    """index 번 규칙(0부터)을 지우고, 지운 규칙을 돌려준다."""
    index = int(index)
    if not 0 <= index < len(rules):   # 음수 번호는 뒤에서 세는 파이썬 동작이 되므로 막는다
        raise ValueError(f"{index}번 규칙이 없습니다")
    return rules.pop(index)


def matches(rule, e):
    """규칙의 조건을 모두 만족하는가. 키워드는 하나라도 메모에 있으면 만족."""
    keywords = rule.get("keywords") or []
    memo = e.get("memo") or ""
    if keywords and not any(k in memo for k in keywords):
        return False
    if rule.get("payer") is not None and e.get("payer") != rule["payer"]:
        return False
    amount = money.to_won(e["amount"])
    if rule.get("min_amount") is not None and amount < rule["min_amount"]:
        return False
    if rule.get("max_amount") is not None and amount > rule["max_amount"]:
        return False
    return True


def classify(e, rules):
    """맞는 규칙 가운데 우선순위가 가장 높은 규칙의 분류. 같으면 먼저 등록한 규칙. 없으면 None."""
    best = None
    for rule in rules:
        # ">" 이므로 우선순위가 같으면 앞(먼저 등록한) 규칙이 남는다
        if matches(rule, e) and (best is None or rule.get("priority", 0) > best.get("priority", 0)):
            best = rule
    return best["category"] if best else None


def apply_rules(store, rules, preview=False):
    """전체 지출을 다시 분류한다. 직접 정한 분류(고정)는 건너뛴다.
    돌려주는 값: 바뀌는 목록 [(번호, 이전 분류, 새 분류)]. preview=True 면 실제로 바꾸지 않는다."""
    changes = []
    for e in store.data["expenses"]:
        # 삭제 표시(규약 6-1)·고정(category_fixed, 없는 옛 지출은 False)·확정 기간(규약 6)은 건너뜀
        if e.get("deleted", False) or e.get("category_fixed", False) or is_locked(store, e["date"]):
            continue
        new = classify(e, rules)
        old = category_of(e)
        if new is None or new == old:   # 맞는 규칙이 없으면 원래 분류를 그대로 둔다
            continue
        changes.append((e["id"], old, new))
        if not preview:
            before = dict(e)
            e["category"] = new
            store.record("edit", e["id"], before, e)
    return changes


def set_category(store, eid, category):
    """분류를 직접 정한다. 다시 분류해도 바뀌지 않게 고정한다."""
    raise NotImplementedError("이 함수를 구현한다")


def unfix_category(store, eid):
    raise NotImplementedError("이 함수를 구현한다")


def uncategorized(store):
    """분류가 "미분류"인 지출 목록(삭제 표시 제외, 날짜·번호 순)."""
    result = [e for e in store.data["expenses"]
              if not e.get("deleted", False) and category_of(e) == UNCATEGORIZED]
    return sorted(result, key=lambda e: (e["date"], e["id"]))


def overlaps(rules):
    """같은 키워드가 서로 다른 분류의 규칙에 함께 있는 경우. [(규칙 번호 i, 규칙 번호 j, 겹친 키워드)]"""
    raise NotImplementedError("이 함수를 구현한다")


def summary(store, start, end):
    """분류별 건수·금액(공통 모듈의 분류 조회 사용)."""
    raise NotImplementedError("이 함수를 구현한다")
