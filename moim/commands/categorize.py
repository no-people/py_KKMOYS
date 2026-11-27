"""명령 묶음 `cat`(분류 규칙). 담당: 기능 2.

add_parser 에서 하위 명령과 인자를 만들고, run 에서 하위 명령을 실행한다.
run 은 자료를 바꿨으면 True 를 돌려준다(통합 실행 틀이 그때만 저장한다).
인자 해석은 common/cliutil.py 의 _members(참여자), _weights(비율), _period(기간)를 쓴다.
"""

from ..common import money
from ..common.queries import category_of
from ..common.rules import UNCATEGORIZED
from ..features import categorize

GROUP = 'cat'


def add_parser(sub, period_args):
    grp = sub.add_parser(GROUP, help="분류 규칙").add_subparsers(dest="cmd", required=True)
    add = grp.add_parser("add", help="규칙 추가")
    add.add_argument("category", help="분류 이름(예: 식비, 장소, 교통)")
    add.add_argument("--keywords", nargs="+", help="메모에 하나라도 있으면 맞는 키워드(띄어 써서 여러 개)")
    add.add_argument("--priority", type=int, default=0, help="클수록 먼저(기본 0)")
    add.add_argument("--payer", help="이 사람이 낸 지출만")
    add.add_argument("--min", dest="min_amount", help="이 금액(원) 이상만")
    add.add_argument("--max", dest="max_amount", help="이 금액(원) 이하만")
    remove = grp.add_parser("remove", help="규칙 삭제")
    remove.add_argument("index", type=int, help="cat list 의 규칙 번호")
    grp.add_parser("list", help="규칙 목록")
    apply = grp.add_parser("apply", help="규칙으로 전체 지출 다시 분류(직접 정한 분류는 그대로)")
    apply.add_argument("--preview", action="store_true", help="바뀔 목록만 보이고 자료는 바꾸지 않음")
    grp.add_parser("uncat", help="미분류 지출 목록")
    fix = grp.add_parser("set", help="분류 직접 지정(다시 분류해도 바뀌지 않게 고정)")
    fix.add_argument("eid", type=int, help="지출 번호")
    fix.add_argument("category", help="분류 이름(예: 식비, 장소, 교통)")
    unfix = grp.add_parser("unfix", help="직접 지정한 분류의 고정 풀기(분류 이름은 그대로)")
    unfix.add_argument("eid", type=int, help="지출 번호")
    return grp


def _rules_path(cfg):
    # 규칙 파일 위치는 설정의 rules 항목(config.example.json)
    path = cfg.get("rules")
    if not path:
        raise ValueError("설정 파일에 분류 규칙 파일(rules) 항목이 없습니다")
    return path


def _describe(i, rule):
    """규칙 한 줄 설명. 예: '0. 식비  키워드: 저녁, 점심  우선순위: 0'"""
    parts = [f"{i}. {rule['category']}"]
    if rule.get("keywords"):
        parts.append("키워드: " + ", ".join(rule["keywords"]))
    if rule.get("payer") is not None:
        parts.append(f"낸 사람: {rule['payer']}")
    if rule.get("min_amount") is not None or rule.get("max_amount") is not None:
        low = money.fmt(rule["min_amount"]) + "원" if rule.get("min_amount") is not None else ""
        high = money.fmt(rule["max_amount"]) + "원" if rule.get("max_amount") is not None else ""
        parts.append(f"금액: {low}~{high}")
    parts.append(f"우선순위: {rule.get('priority', 0)}")
    return "  ".join(parts)


def run(c, args, cfg, store, out):
    # set·unfix 는 규칙 파일을 쓰지 않으므로 rules 설정이 없어도 된다
    if c == "set":
        e = categorize.set_category(store, args.eid, args.category)
        out(f"분류 지정 {e['id']}번: {e['category']} (고정, cat unfix {e['id']} 로 풀기)")
        return True   # 자료가 바뀌었으니 저장
    if c == "unfix":
        e = categorize.unfix_category(store, args.eid)
        out(f"분류 고정 풀기 {e['id']}번: {category_of(e)} (다음 cat apply 때 규칙을 따름)")
        return True
    path = _rules_path(cfg)
    if c == "add":
        rules = categorize.load_rules(path)
        rule = categorize.add_rule(rules, args.category, args.keywords, args.priority,
                                   args.payer, args.min_amount, args.max_amount)
        categorize.save_rules(path, rules)
        out("규칙 추가: " + _describe(len(rules) - 1, rule))
        return False   # 규칙 파일만 바뀌고 자료 파일은 그대로
    if c == "remove":
        rules = categorize.load_rules(path)
        rule = categorize.remove_rule(rules, args.index)
        categorize.save_rules(path, rules)
        out(f"규칙 삭제: {args.index}. {rule['category']}")
        return False
    if c == "list":
        rules = categorize.load_rules(path)
        if not rules:
            out("등록된 규칙이 없습니다")
        for i, rule in enumerate(rules):
            out(_describe(i, rule))
        return False
    if c == "apply":
        changes = categorize.apply_rules(store, categorize.load_rules(path), preview=args.preview)
        for eid, old, new in changes:
            out(f"{eid}번: {old} → {new}")
        if args.preview:
            out(f"(미리 보기) {len(changes)}건이 바뀝니다. 자료는 바꾸지 않았습니다")
            return False
        out(f"{len(changes)}건을 다시 분류했습니다")
        return bool(changes)   # 바뀐 지출이 있을 때만 저장
    if c == "uncat":
        items = categorize.uncategorized(store)
        for e in items:
            memo = e.get("memo") or ""
            out(f"{e['id']}번  {e['date']}  {money.fmt(money.to_won(e['amount']))}원  {e['payer']}  {memo}".rstrip())
        out(f"{UNCATEGORIZED} {len(items)}건")
        return False
    raise ValueError(f"모르는 분류 규칙 명령입니다: {c}")
