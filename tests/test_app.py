import unittest
import os
import io
import shutil
import tempfile
import pandas as pd

from app import create_app
from config import TestingConfig
from services.db_service import init_db


class TestAutoBIApp(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = TestingConfig()
        self.config.UPLOAD_FOLDER = os.path.join(self.test_dir, "uploads")
        self.config.CACHE_FOLDER = os.path.join(self.test_dir, "cache")
        self.config.DATA_FOLDER = os.path.join(self.test_dir, "data")
        self.config.DB_PATH = os.path.join(self.test_dir, "data", "test.db")
        self.config.LOG_FILE = os.path.join(self.test_dir, "test.log")
        
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "AutoBI")

    def test_index_route(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AutoBI", response.data)

    def test_404_error_page(self):
        response = self.client.get("/non-existent-page-12345")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Page Not Found", response.data)

    def test_upload_invalid_file_extension(self):
        data = {
            "file": (io.BytesIO(b"malicious script"), "exploit.exe")
        }
        response = self.client.post("/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Unsupported file format", response.data)

    def test_upload_valid_csv_and_redirect(self):
        csv_content = b"Department,Budget,Headcount\nEngineering,500000,25\nSales,300000,15\n"
        data = {
            "file": (io.BytesIO(csv_content), "departments.csv")
        }
        response = self.client.post("/upload", data=data, content_type="multipart/form-data")
        # Should redirect to /dashboard/<file_id>?sheet=Data
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard/", response.headers["Location"])

        # Follow redirect
        dashboard_res = self.client.get(response.headers["Location"])
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertIn(b"departments.csv", dashboard_res.data)
        self.assertIn(b"Engineering", dashboard_res.data)


if __name__ == "__main__":
    unittest.main()

