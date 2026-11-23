"""글자 표와 막대그래프. 보고서·지출 목록·정산·예산 명령이 함께 쓴다."""

import unicodedata

from . import money


def width(text):
    """화면 폭. 한글 등 넓은 글자는 2칸."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(text))


def pad(text, w, right=False):
    gap = w - width(text)
    return (" " * gap + str(text)) if right else (str(text) + " " * gap)


def table(headers, rows, total=None, numeric=None):
    """글자 표를 만들어 돌려준다. 담당: 기능 3"""
    num_cols = set(numeric) if numeric else set()
    col_count = len(headers)

    def format_cell(val):
        if isinstance(val, int) and not isinstance(val, bool):
            return money.fmt(val)
        return str(val)

    str_headers = [str(h) for h in headers]
    str_rows = [[format_cell(row[i]) for i in range(col_count)] for row in rows]
    str_total = [format_cell(total[i]) for i in range(col_count)] if total is not None else None

    widths = [width(h) for h in str_headers]
    for r in str_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], width(cell))
    if str_total is not None:
        for i, cell in enumerate(str_total):
            widths[i] = max(widths[i], width(cell))

    def render_row(cells, align_numeric):
        rendered = "  ".join(
            pad(cell, widths[i], right=(align_numeric and i in num_cols))
            for i, cell in enumerate(cells)
        )
        return rendered.rstrip()

    sep = "  ".join("-" * w for w in widths)
    lines = [render_row(str_headers, align_numeric=False), sep]
    for r in str_rows:
        lines.append(render_row(r, align_numeric=True))
    if str_total is not None:
        lines.append(sep)
        lines.append(render_row(str_total, align_numeric=True))
    return "\n".join(lines)

def bar_chart(data, bar_width=30, char="#"):
    """{이름: 값} 을 글자 막대그래프로."""
    raise NotImplementedError("기능 3 담당이 구현한다")
