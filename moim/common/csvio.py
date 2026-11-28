"""CSV 읽기: 글자 인코딩 판별(UTF-8·CP949)과 열 이름 연결. 가져오기(기능 6)와 은행 거래내역 가져오기(기능 5)가 함께 쓴다."""

import codecs
import csv
import os


def detect_encoding(path):
    """UTF-8(BOM 포함)로 읽히면 utf-8-sig, 아니면 cp949. 둘 다 안 되면 ValueError."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    for enc in ("utf-8-sig", "cp949"):
        decoder = codecs.getincrementaldecoder(enc)()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
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
            reader = csv.reader(f)
            try:
                raw_headers = next(reader)
            except StopIteration:
                return enc, []

            headers = [h.strip() for h in raw_headers]
            if not headers or any(not h for h in headers):
                raise ValueError(f"CSV 머리글이 비어 있거나 빈 열 이름이 있습니다: {path}")
            if len(set(headers)) != len(headers):
                raise ValueError(f"CSV 머리글에 중복된 열 이름이 있습니다: {path}")

            col_map = dict(mapping) if mapping else {}
            rows = []
            prev_line = reader.line_num
            for raw_cells in reader:
                start_line = prev_line + 1
                prev_line = reader.line_num
                if not raw_cells:
                    continue
                cleaned = [c.strip() for c in raw_cells]
                if all(c == "" for c in cleaned):
                    continue
                if len(cleaned) != len(headers):
                    raise ValueError(f"{start_line}번째 줄 열 개수가 머리글과 다릅니다: {path}")
                mapped = {
                    col_map.get(header, header): value
                    for header, value in zip(headers, cleaned)
                }
                rows.append((start_line, mapped))
    except (UnicodeDecodeError, LookupError) as exc:
        raise ValueError(f"글자 인코딩({enc})으로 읽을 수 없습니다: {path}") from exc
    return enc, rows
