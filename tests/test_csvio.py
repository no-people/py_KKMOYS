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

    def test_read_csv_rows_cp949_with_mapping_and_line_numbers(self):
        path = self._path("expenses_cp949.csv")
        content = "지출일,결제자,금액,비고\n2026-11-01, 김민수 , 12000 , 점심 \n,,,\n2026-11-02,이서연,8000,커피\n"
        with open(path, "w", encoding="cp949", newline="") as f:
            f.write(content)

        enc, rows = csvio.read_csv_rows(
            path,
            mapping={"지출일": "date", "결제자": "payer", "금액": "amount"},
        )
        self.assertEqual(enc, "cp949")
        self.assertEqual(len(rows), 2)
        first_row, second_row = rows
        self.assertEqual(first_row, (2, {"date": "2026-11-01", "payer": "김민수", "amount": "12000", "비고": "점심"}))
        self.assertEqual(second_row, (4, {"date": "2026-11-02", "payer": "이서연", "amount": "8000", "비고": "커피"}))

    def test_read_csv_rows_errors(self):
        path = self._path("cols.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("date,amount\n2026-11-01,1000\n")
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(path, mapping={"지출일": "date"})

        empty_path = self._path("empty.csv")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(empty_path)

        extra_col_path = self._path("extra.csv")
        with open(extra_col_path, "w", encoding="utf-8") as f:
            f.write("date,amount\n2026-11-01,1000,extra\n")
        with self.assertRaises(ValueError):
            csvio.read_csv_rows(extra_col_path)


if __name__ == "__main__":
    unittest.main()
