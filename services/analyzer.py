import logging
import math
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

ID_COLUMN_KEYWORDS = {"id", "code", "zip", "postal", "ssn", "phone", "key", "uuid", "row_id", "index"}


def is_likely_id_column(column_name: str, series: pd.Series) -> bool:
    """Check if a column is an identifier rather than a statistical measure/category."""
    name_clean = str(column_name).lower().strip().replace(" ", "_")
    
    # Keyword check
    if any(kw in name_clean for kw in ID_COLUMN_KEYWORDS):
        return True

    # High cardinality check (almost every row is unique)
    non_null_count = series.count()
    if non_null_count > 20 and series.nunique() / non_null_count > 0.95:
        return True

    return False


def detect_date_columns(df: pd.DataFrame) -> list:
    """
    Detect columns containing dates with defensive checks to prevent accidental type coercion.
    """
    date_columns = []
    if df.empty:
        return date_columns

    for column in df.columns:
        # Already datetime
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            date_columns.append(column)
            continue

        # Check object or string columns
        if pd.api.types.is_object_dtype(df[column]) or pd.api.types.is_string_dtype(df[column]):
            non_null = df[column].dropna()
            if len(non_null) == 0:
                continue

            # Don't try parsing if sample strings look purely numeric or extremely long
            sample = non_null.head(50).astype(str)
            if sample.str.isnumeric().all():
                continue

            try:
                converted = pd.to_datetime(sample, errors="coerce")
                success_rate = converted.notna().mean()
                if success_rate >= 0.8:
                    df[column] = pd.to_datetime(df[column], errors="coerce")
                    date_columns.append(column)
            except Exception:
                pass

    return date_columns


def detect_column_types(df: pd.DataFrame) -> dict:
    """
    Classify dataset columns into numeric, categorical, date, and identifier groups.
    """
    if df.empty:
        return {"numeric": [], "categorical": [], "date": [], "id": []}

    date_columns = detect_date_columns(df)
    numeric_columns = []
    categorical_columns = []
    id_columns = []

    for column in df.columns:
        if column in date_columns:
            continue

        series = df[column]

        # Numeric detection
        if pd.api.types.is_numeric_dtype(series):
            # Check if this numeric column is an ID or Year/Postal Code
            if is_likely_id_column(column, series):
                id_columns.append(column)
                # Keep in numeric only if non-ID
            else:
                numeric_columns.append(column)
        else:
            if is_likely_id_column(column, series):
                id_columns.append(column)
            categorical_columns.append(column)

    return {
        "numeric": numeric_columns,
        "categorical": categorical_columns,
        "date": date_columns,
        "id": id_columns
    }


def format_number(value) -> str:
    """
    Human-readable formatting for large numbers and currency/metric values.
    """
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "N/A"

    try:
        val = float(value)
        sign = "-" if val < 0 else ""
        abs_val = abs(val)

        if abs_val >= 1_000_000_000:
            return f"{sign}{abs_val / 1_000_000_000:.2f}B"
        elif abs_val >= 1_000_000:
            return f"{sign}{abs_val / 1_000_000:.2f}M"
        elif abs_val >= 1_000:
            return f"{sign}{abs_val / 1_000:.2f}K"
        elif val.is_integer():
            return f"{int(val):,}"
        else:
            return f"{val:,.2f}"
    except Exception:
        return str(value)


def generate_kpis(df: pd.DataFrame, column_types: dict) -> list:
    """
    Automatically create high-impact KPI cards.
    """
    kpis = []
    if df.empty:
        return [
            {"title": "Total Records", "value": "0", "icon": "bi-table"},
            {"title": "Columns", "value": str(len(df.columns)), "icon": "bi-layout-three-columns"},
            {"title": "Missing Values", "value": "0", "icon": "bi-exclamation-triangle"},
            {"title": "Status", "value": "No Data", "icon": "bi-info-circle"}
        ]

    # Baseline system KPIs
    kpis.append({
        "title": "Total Records",
        "value": f"{len(df):,}",
        "icon": "bi-table"
    })

    kpis.append({
        "title": "Columns",
        "value": str(len(df.columns)),
        "icon": "bi-layout-three-columns"
    })

    missing_values = int(df.isnull().sum().sum())
    kpis.append({
        "title": "Missing Values",
        "value": f"{missing_values:,}",
        "icon": "bi-exclamation-triangle"
    })

    duplicates = int(df.duplicated().sum())
    kpis.append({
        "title": "Duplicate Rows",
        "value": f"{duplicates:,}",
        "icon": "bi-copy"
    })

    # Numeric KPI metrics
    numeric_columns = column_types.get("numeric", [])
    for column in numeric_columns[:4]:
        total = df[column].sum(skipna=True)
        avg = df[column].mean(skipna=True)
        kpis.append({
            "title": f"Total {column}",
            "value": format_number(total),
            "subtitle": f"Avg: {format_number(avg)}",
            "icon": "bi-graph-up-arrow"
        })

    return kpis


def generate_summary(df: pd.DataFrame, column_types: dict) -> dict:
    """
    High-level dataset summary metrics.
    """
    if df.empty:
        return {
            "rows": 0,
            "columns": len(df.columns),
            "numeric_columns": 0,
            "categorical_columns": 0,
            "date_columns": 0,
            "missing_values": 0,
            "duplicates": 0,
            "completeness": 0.0
        }

    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isnull().sum().sum())

    if total_cells > 0:
        completeness = ((total_cells - missing_cells) / total_cells) * 100.0
    else:
        completeness = 0.0

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "numeric_columns": len(column_types.get("numeric", [])),
        "categorical_columns": len(column_types.get("categorical", [])),
        "date_columns": len(column_types.get("date", [])),
        "missing_values": missing_cells,
        "duplicates": int(df.duplicated().sum()),
        "completeness": round(completeness, 2)
    }


def get_column_information(df: pd.DataFrame) -> list:
    """
    Information shown in the Data Overview and schema table.
    """
    information = []
    if df.empty:
        return information

    total_rows = len(df)
    for column in df.columns:
        missing_count = int(df[column].isnull().sum())
        missing_pct = round((missing_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
        unique_count = int(df[column].nunique(dropna=True))

        information.append({
            "column": column,
            "dtype": str(df[column].dtype),
            "missing": missing_count,
            "unique": unique_count,
            "missing_percentage": missing_pct
        })

    return information
