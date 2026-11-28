import os
import tempfile
import unittest
from moim.common import csvio


class TestCsvio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_detect_encoding_utf8_bom_and_cp949(self):
        utf8_path = self._path("utf8.csv")
        with open(utf8_path, "w", encoding="utf-8") as f:
            f.write("날짜,금액\n2026-11-01,1000\n")
        self.assertEqual(csvio.detect_encoding(utf8_path), "utf-8-sig")

        bom_path = self._path("bom.csv")
        with open(bom_path, "w", encoding="utf-8-sig") as f:
            f.write("날짜,금액\n2026-11-01,1000\n")
        self.assertEqual(csvio.detect_encoding(bom_path), "utf-8-sig")

        cp949_path = self._path("cp949.csv")
        with open(cp949_path, "w", encoding="cp949") as f:
            f.write("날짜,금액\n2026-11-01,1000\n")
        self.assertEqual(csvio.detect_encoding(cp949_path), "cp949")

    def test_detect_encoding_invalid_and_missing(self):
        bad_path = self._path("broken.csv")
        with open(bad_path, "wb") as f:
            f.write(b"\xff\xfe\xfd\x80\x81")
        with self.assertRaises(ValueError):
            csvio.detect_encoding(bad_path)

        with self.assertRaises(FileNotFoundError):
            csvio.detect_encoding(self._path("missing.csv"))

    def test_read_csv_rows_line_number_after_blank_line(self):
        path = self._path("blank_line.csv")
        content = "날짜,내용,출금액\n2026-11-01,점심,12000\n\n2026-11-02,커피,4500\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        enc, rows = csvio.read_csv_rows(
            path,
            mapping={"날짜": "date", "내용": "memo", "출금액": "amount"},
        )
        self.assertEqual(enc, "utf-8-sig")
        first_row, second_row = rows
        self.assertEqual(first_row, (2, {"date": "2026-11-01", "memo": "점심", "amount": "12000"}))
        self.assertEqual(second_row, (4, {"date": "2026-11-02", "memo": "커피", "amount": "4500"}))

    def test_read_csv_rows_line_number_after_multiline_cell(self):
        path = self._path("multiline.csv")
        content = '날짜,메모,금액\n2026-11-01,"첫째 줄\n둘째 줄",15000\n2026-11-02,다음 행,8000\n'
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)

        _, rows = csvio.read_csv_rows(path, mapping={"날짜": "date", "메모": "memo", "금액": "amount"})
        first_row, second_row = rows
        self.assertEqual(first_row, (2, {"date": "2026-11-01", "memo": "첫째 줄\n둘째 줄", "amount": "15000"}))
        self.assertEqual(second_row, (4, {"date": "2026-11-02", "memo": "다음 행", "amount": "8000"}))

    def test_read_csv_rows_header_trim_reordered_columns_and_explicit_encoding(self):
        path = self._path("reordered_cp949.csv")
        content = " 금액 , 날짜 , 낸사람 , 비고 \n 9000 , 2026-11-03 , 김민수 , 간식 \n"
        with open(path, "w", encoding="cp949", newline="") as f:
            f.write(content)

        enc, rows = csvio.read_csv_rows(
            path,
            mapping={"날짜": "date", "낸사람": "payer", "금액": "amount"},
            encoding="cp949",
        )
        self.assertEqual(enc, "cp949")
        self.assertEqual(rows, list(((2, {"amount": "9000", "date": "2026-11-03", "payer": "김민수", "비고": "간식"}),)))

        with self.assertRaises(ValueError):
            csvio.read_csv_rows(path, encoding="utf-8-sig")

    def test_read_csv_rows_errors_and_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            csvio.read_csv_rows(self._path("not_exist.csv"))

        empty_path = self._path("empty.csv")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")
        self.assertEqual(csvio.read_csv_rows(empty_path), ("utf-8-sig", list()))

        unknown_enc_path = self._path("plain.csv")
        with open(unknown_enc_path, "w", encoding="utf-8") as f:
            f.write("date,amount\n2026-11-01,1000\n")
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(unknown_enc_path, encoding="nope")

        extra_col_path = self._path("extra.csv")
        with open(extra_col_path, "w", encoding="utf-8") as f:
            f.write("date,amount\n2026-11-01,1000,extra\n")
        with self.assertRaises(ValueError) as cm:
            csvio.read_csv_rows(extra_col_path)
        self.assertIn("2번째 줄", str(cm.exception))

        short_col_path = self._path("short.csv")
        with open(short_col_path, "w", encoding="utf-8") as f:
            f.write("date,payer,amount\n2026-11-01,김민수\n")
        with self.assertRaises(ValueError) as cm2:
            csvio.read_csv_rows(short_col_path)
        self.assertIn("2번째 줄", str(cm2.exception))


if __name__ == "__main__":
    unittest.main()
