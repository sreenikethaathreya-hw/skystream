import io
import math
import re
from datetime import datetime

import pandas as pd

from app.ingest.report import ImportFailure

EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xls")
# Row numbers in reports match what the admin sees in Excel: header is row 1.
FIRST_DATA_ROW = 2


def read_upload(content: bytes, filename: str, preferred_sheets: list[str]) -> pd.DataFrame:
    name = filename.lower()
    try:
        if name.endswith(".csv"):
            try:
                frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            except UnicodeDecodeError:
                frame = pd.read_csv(io.BytesIO(content), encoding="latin-1")
        elif name.endswith(EXCEL_SUFFIXES):
            sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
            by_lower = {str(k).strip().lower(): k for k in sheets}
            chosen = next((by_lower[s.lower()] for s in preferred_sheets if s.lower() in by_lower), None)
            frame = sheets[chosen if chosen is not None else next(iter(sheets))]
        else:
            raise ImportFailure("Upload a .xlsx or .csv file")
    except ImportFailure:
        raise
    except Exception as exc:  # pandas raises many parser-specific types
        raise ImportFailure(f"Could not read the file: {exc}") from exc
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame


def require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ImportFailure(f"Missing required columns: {', '.join(missing)}")


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def to_float(value) -> float | None:
    if is_blank(value):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(" ", "").replace("\xa0", ""))
    except ValueError:
        return None


def to_int(value) -> int | None:
    number = to_float(value)
    if number is None or number != int(number):
        return None
    return int(number)


def to_text(value) -> str | None:
    if is_blank(value):
        return None
    return " ".join(str(value).replace("\xa0", " ").split())


def to_datetime(value) -> datetime | None:
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.to_pydatetime()


def records(frame: pd.DataFrame) -> list[tuple[int, dict]]:
    return [(i + FIRST_DATA_ROW, row) for i, row in enumerate(frame.to_dict(orient="records"))]


YEAR_PCT = re.compile(r"^(\d{4})%$")
