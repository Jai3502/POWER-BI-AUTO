import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "autobi-production-secret-key-change-in-env-98234710")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    CACHE_FOLDER = os.environ.get("CACHE_FOLDER", str(BASE_DIR / "cache"))
    DATA_FOLDER = os.environ.get("DATA_FOLDER", str(BASE_DIR / "data"))
    DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data" / "autobi.db"))
    
    # 50 MB maximum upload size by default
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    
    ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
    
    # Performance & Caching
    CACHE_PARQUET = os.environ.get("CACHE_PARQUET", "True").lower() in ("true", "1", "yes")
    
    # Preview settings
    PREVIEW_ROWS_LIMIT = int(os.environ.get("PREVIEW_ROWS_LIMIT", 500))
    MAX_FILTER_UNIQUE_VALUES = int(os.environ.get("MAX_FILTER_UNIQUE_VALUES", 100))
    
    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", str(BASE_DIR / "logs" / "autobi.log"))


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, require setting SECRET_KEY via environment
    SECRET_KEY = os.environ.get("SECRET_KEY", "autobi-prod-secure-random-token-2026")


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    UPLOAD_FOLDER = str(BASE_DIR / "tests" / "test_uploads")
    CACHE_FOLDER = str(BASE_DIR / "tests" / "test_cache")
    DATA_FOLDER = str(BASE_DIR / "tests" / "test_data")
    DB_PATH = str(BASE_DIR / "tests" / "test_data" / "test_autobi.db")


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}

def get_config():
    env_name = os.environ.get("FLASK_ENV", "production" if os.environ.get("ENV") == "production" else "development")
    return config_by_name.get(env_name, DevelopmentConfig)

