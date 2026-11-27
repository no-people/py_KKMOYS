"""CSV 읽기: 글자 인코딩 판별(UTF-8·CP949)과 열 이름 연결. 가져오기(기능 6)와 은행 거래내역 가져오기(기능 5)가 함께 쓴다."""

import csv
import os


def detect_encoding(path):
    """UTF-8(BOM 포함)로 읽히면 utf-8-sig, 아니면 cp949. 둘 다 안 되면 ValueError."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"지원하지 않는 글자 인코딩입니다: {path}")


def read_csv_rows(path, mapping=None, encoding=None):
    """CSV 를 읽어 (인코딩, [(줄 번호, {필드: 값})]) 를 돌려준다. mapping: {파일 열 이름: 필드 이름}"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    enc = encoding or detect_encoding(path)
    try:
        with open(path, encoding=enc, newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError(f"CSV 머리글이 없습니다: {path}")
            headers = [h.strip() if h is not None else "" for h in reader.fieldnames]
            if any(not h for h in headers):
                raise ValueError(f"CSV 머리글에 빈 열 이름이 있습니다: {path}")
            if len(set(headers)) != len(headers):
                raise ValueError(f"CSV 머리글에 중복된 열 이름이 있습니다: {path}")
            reader.fieldnames = headers

            col_map = dict(mapping) if mapping else {}
            missing = [src for src in col_map if src not in headers]
            if missing:
                raise ValueError(f"필수 열이 없습니다({', '.join(missing)}): {path}")

            rows = []
            for lineno, raw_row in enumerate(reader, start=2):
                if None in raw_row:
                    raise ValueError(f"{lineno}번째 줄 열 개수가 머리글과 다릅니다: {path}")
                cleaned = {k: (v.strip() if v is not None else "") for k, v in raw_row.items()}
                if all(v == "" for v in cleaned.values()):
                    continue
                mapped = {col_map.get(k, k): v for k, v in cleaned.items()}
                rows.append((lineno, mapped))
    except UnicodeDecodeError as exc:
        raise ValueError(f"글자 인코딩({enc})으로 읽을 수 없습니다: {path}") from exc
    return enc, rows
