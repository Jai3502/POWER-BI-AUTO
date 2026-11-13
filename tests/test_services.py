import unittest
import os
import shutil
import tempfile
import pandas as pd

from services.excel_service import (
    allowed_file,
    get_file_type,
    detect_csv_delimiter,
    load_excel,
    save_cached_data,
    load_cached_data,
    export_dataframe_bytes
)
from services.analyzer import (
    detect_column_types,
    format_number,
    generate_kpis,
    generate_summary,
    get_column_information
)
from services.db_service import (
    init_db,
    save_file_record,
    get_file_record,
    list_recent_files
)


class TestAutoBIServices(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test.db")
        init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_allowed_file(self):
        self.assertTrue(allowed_file("sales.xlsx"))
        self.assertTrue(allowed_file("data.xls"))
        self.assertTrue(allowed_file("records.csv"))
        self.assertFalse(allowed_file("script.py"))
        self.assertFalse(allowed_file("hack.exe"))
        self.assertFalse(allowed_file(""))

    def test_get_file_type(self):
        self.assertEqual(get_file_type("file.csv"), "csv")
        self.assertEqual(get_file_type("file.xlsx"), "excel")
        self.assertEqual(get_file_type("file.xls"), "excel")

    def test_csv_delimiter_and_loading(self):
        csv_path = os.path.join(self.test_dir, "test.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("Region,Sales,Quantity\nNorth,1500,10\nSouth,2300,15\n")

        delim = detect_csv_delimiter(csv_path)
        self.assertEqual(delim, ",")

        df = load_excel(csv_path, sheet_name="Data")
        self.assertEqual(len(df), 2)
        self.assertIn("Region", df.columns)
        self.assertIn("Sales", df.columns)

    def test_caching_layer(self):
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["X", "Y", "Z"]})
        cache_dir = os.path.join(self.test_dir, "cache")
        save_cached_data(cache_dir, "file_123", "Sheet1", df)

        cached_df = load_cached_data(cache_dir, "file_123", "Sheet1")
        self.assertIsNotNone(cached_df)
        self.assertEqual(len(cached_df), 3)
        self.assertEqual(list(cached_df.columns), ["A", "B"])

    def test_export_bytes(self):
        df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [95, 88]})
        csv_bytes, mime, ext = export_dataframe_bytes(df, "csv")
        self.assertIn(b"Alice", csv_bytes)
        self.assertEqual(ext, "csv")

        xlsx_bytes, mime_x, ext_x = export_dataframe_bytes(df, "xlsx")
        self.assertTrue(len(xlsx_bytes) > 0)
        self.assertEqual(ext_x, "xlsx")

    def test_number_formatting(self):
        self.assertEqual(format_number(1250000000), "1.25B")
        self.assertEqual(format_number(3400000), "3.40M")
        self.assertEqual(format_number(15000), "15.00K")
        self.assertEqual(format_number(25), "25")
        self.assertEqual(format_number(-5000000), "-5.00M")
        self.assertEqual(format_number(None), "N/A")

    def test_analyzer_classification(self):
        df = pd.DataFrame({
            "Order_Date": pd.date_range("2026-01-01", periods=5),
            "Revenue": [100.5, 200.0, 300.2, 400.0, 500.1],
            "Category": ["Tech", "Home", "Tech", "Office", "Home"],
            "Customer_ID": ["C101", "C102", "C103", "C104", "C105"]
        })
        types = detect_column_types(df)
        self.assertIn("Order_Date", types["date"])
        self.assertIn("Revenue", types["numeric"])
        self.assertIn("Category", types["categorical"])

        kpis = generate_kpis(df, types)
        self.assertTrue(len(kpis) >= 4)

        summary = generate_summary(df, types)
        self.assertEqual(summary["rows"], 5)
        self.assertEqual(summary["completeness"], 100.0)

    def test_db_persistence(self):
        save_file_record(
            db_path=self.db_path,
            file_id="uuid-1",
            original_name="sales.xlsx",
            stored_filename="uuid-1_sales.xlsx",
            file_path="/tmp/sales.xlsx",
            file_type="excel",
            file_size=1024,
            sheets=["Sales", "Orders"]
        )
        rec = get_file_record(self.db_path, "uuid-1")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["original_name"], "sales.xlsx")
        self.assertEqual(rec["sheets"], ["Sales", "Orders"])

        recent = list_recent_files(self.db_path)
        self.assertEqual(len(recent), 1)


if __name__ == "__main__":
    unittest.main()

