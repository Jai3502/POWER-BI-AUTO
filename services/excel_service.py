import os
import io
import csv
import logging
import hashlib
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}


def allowed_file(filename: str) -> bool:
    """Check whether uploaded file extension is supported."""
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename: str) -> str:
    """Return normalized file type: 'excel' or 'csv'."""
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return "csv" if ext == "csv" else "excel"


def detect_csv_delimiter(file_path: str, default: str = ",") -> str:
    """Sniff delimiter of a CSV file automatically."""
    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            sample = f.read(8192)
            if not sample:
                return default
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=[",", ";", "\t", "|"])
            return dialect.delimiter
    except Exception as e:
        logger.warning("Could not sniff delimiter for %s, falling back to %s: %s", file_path, default, e)
        return default


def get_sheet_names(file_path: str) -> list:
    """Return all worksheet names for Excel, or ['Data'] for CSV."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return ["Data"]

    try:
        excel_file = pd.ExcelFile(file_path)
        sheets = excel_file.sheet_names
        if not sheets:
            raise ValueError("The Excel file contains no worksheets.")
        return sheets
    except Exception as e:
        logger.error("Error inspecting Excel sheets for %s: %s", file_path, e)
        raise ValueError(f"Unable to read Excel workbook: {str(e)}")


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean empty rows/columns and normalize column names."""
    if df.empty:
        return df

    # Drop rows that are completely empty
    df = df.dropna(how="all")

    # Drop columns that are completely empty
    df = df.dropna(axis=1, how="all")

    # Clean and sanitize column names
    clean_cols = []
    seen = {}
    for i, col in enumerate(df.columns):
        c_str = str(col).strip()
        if not c_str or c_str.lower().startswith("unnamed:"):
            c_str = f"Column_{i + 1}"
        # Ensure column uniqueness
        if c_str in seen:
            seen[c_str] += 1
            c_str = f"{c_str}_{seen[c_str]}"
        else:
            seen[c_str] = 0
        clean_cols.append(c_str)

    df.columns = clean_cols
    return df


def _get_cache_path(cache_folder: str, file_id: str, sheet_name: str) -> str:
    """Generate safe filename for cached dataframe."""
    sheet_hash = hashlib.md5(sheet_name.encode("utf-8")).hexdigest()[:8]
    safe_name = "".join(c if c.isalnum() else "_" for c in sheet_name)[:20]
    filename = f"{file_id}_{safe_name}_{sheet_hash}.pkl"
    return os.path.join(cache_folder, filename)


def load_cached_data(cache_folder: str, file_id: str, sheet_name: str):
    """Load cached dataframe if present."""
    if not cache_folder or not file_id:
        return None
    cache_path = _get_cache_path(cache_folder, file_id, sheet_name)
    if os.path.exists(cache_path):
        try:
            return pd.read_pickle(cache_path)
        except Exception as e:
            logger.warning("Failed to read cache at %s: %s", cache_path, e)
    return None


def save_cached_data(cache_folder: str, file_id: str, sheet_name: str, df: pd.DataFrame):
    """Save cleaned dataframe to disk cache for sub-second retrieval."""
    if not cache_folder or not file_id:
        return
    try:
        os.makedirs(cache_folder, exist_ok=True)
        cache_path = _get_cache_path(cache_folder, file_id, sheet_name)
        df.to_pickle(cache_path)
    except Exception as e:
        logger.warning("Failed to save dataframe to cache: %s", e)


def load_excel(file_path: str, sheet_name: any = 0, file_id: str = None, 
               cache_folder: str = None, force_reload: bool = False) -> pd.DataFrame:
    """
    Load and clean dataset from Excel or CSV with automated caching.
    """
    sheet_str = str(sheet_name) if sheet_name is not None else "0"

    # Try cache first if available
    if not force_reload and file_id and cache_folder:
        cached_df = load_cached_data(cache_folder, file_id, sheet_str)
        if cached_df is not None:
            return cached_df

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.rsplit(".", 1)[-1].lower()

    if ext == "csv":
        delimiter = detect_csv_delimiter(file_path)
        df = None
        # Try multiple encodings
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(file_path, sep=delimiter, encoding=enc, low_memory=False)
                break
            except (UnicodeDecodeError, Exception):
                continue
        if df is None:
            raise ValueError("Unable to read CSV file. Please verify file encoding.")
    else:
        # Excel loading
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        except Exception as e:
            logger.error("Error reading worksheet '%s' from %s: %s", sheet_name, file_path, e)
            raise ValueError(f"Failed to load worksheet '{sheet_name}': {str(e)}")

    df = _clean_dataframe(df)

    # Cache cleaned dataframe
    if file_id and cache_folder:
        save_cached_data(cache_folder, file_id, sheet_str, df)

    return df


def export_dataframe_bytes(df: pd.DataFrame, file_format: str = "csv") -> tuple[bytes, str, str]:
    """
    Export dataframe to in-memory bytes for direct download.
    Returns: (bytes_data, mimetype, file_extension)
    """
    if file_format.lower() == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
        output.seek(0)
        return (
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx"
        )
    else:
        # Default CSV
        csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        return (csv_data, "text/csv", "csv")
