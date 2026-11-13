import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection(db_path: str):
    """Context manager that guarantees transaction commit and connection closure."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str):
    """Initialize database tables for file metadata and analytics sessions."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sheets_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at)")
    logger.info("Initialized metadata SQLite database at %s", db_path)


def save_file_record(db_path: str, file_id: str, original_name: str, stored_filename: str,
                     file_path: str, file_type: str, file_size: int, sheets: list) -> dict:
    """Store uploaded file metadata."""
    sheets_json = json.dumps(sheets)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO files 
            (file_id, original_name, stored_filename, file_path, file_type, file_size, sheets_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_id,
            original_name,
            stored_filename,
            file_path,
            file_type,
            file_size,
            sheets_json,
            created_at
        ))
    return {
        "file_id": file_id,
        "original_name": original_name,
        "stored_filename": stored_filename,
        "path": file_path,
        "file_type": file_type,
        "file_size": file_size,
        "sheets": sheets
    }


def get_file_record(db_path: str, file_id: str):
    """Retrieve file metadata by file_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_id, original_name, stored_filename, file_path, file_type, file_size, sheets_json, created_at
            FROM files WHERE file_id = ?
        """, (file_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "file_id": row["file_id"],
            "original_name": row["original_name"],
            "stored_filename": row["stored_filename"],
            "path": row["file_path"],
            "file_type": row["file_type"],
            "file_size": row["file_size"],
            "sheets": json.loads(row["sheets_json"]),
            "created_at": row["created_at"]
        }


def list_recent_files(db_path: str, limit: int = 10) -> list:
    """Get recent uploads."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_id, original_name, file_size, created_at
            FROM files ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def delete_file_record(db_path: str, file_id: str) -> bool:
    """Delete metadata for a given file_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
        return cursor.rowcount > 0
