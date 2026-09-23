"""Parse an uploaded CSV/XLSX of URLs into deduped, validated rows."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

_URL_COLUMN_NAMES = {"url", "link"}
_ID_COLUMN_NAMES = {"id"}
_URL_LIKE_RE = re.compile(r"^https?://", re.IGNORECASE)

_validate_url = URLValidator(schemes=["http", "https"])


class InvalidFileError(Exception):
    """Raised when no URL column can be found in the uploaded file."""


@dataclass
class ParsedUrl:
    source_id: str | None
    url: str


@dataclass
class ParseResult:
    urls: list[ParsedUrl]
    skipped: int


def parse_url_file(file) -> ParseResult:
    """Read CSV or XLSX, detect the URL column case-insensitively, validate,
    dedupe (preserving order) and count skipped rows. Raises InvalidFileError
    if no URL column can be found."""
    name = getattr(file, "name", "")
    if name.lower().endswith(".xlsx"):
        df = pd.read_excel(file, engine="openpyxl", dtype=str)
    else:
        df = pd.read_csv(file, dtype=str)
    df = df.fillna("")

    url_column = _find_url_column(df)
    if url_column is None:
        raise InvalidFileError("No URL column found in the uploaded file.")
    id_column = _find_id_column(df)

    seen: set[str] = set()
    urls: list[ParsedUrl] = []
    skipped = 0

    for _, row in df.iterrows():
        raw_url = str(row[url_column]).strip()
        if not raw_url or not _is_valid_url(raw_url):
            skipped += 1
            continue
        if raw_url in seen:
            continue
        seen.add(raw_url)
        source_id = str(row[id_column]).strip() or None if id_column else None
        urls.append(ParsedUrl(source_id=source_id, url=raw_url))

    return ParseResult(urls=urls, skipped=skipped)


def _find_url_column(df: pd.DataFrame) -> str | None:
    for column in df.columns:
        if str(column).strip().lower() in _URL_COLUMN_NAMES:
            return column
    for column in df.columns:
        values = df[column].astype(str).str.strip()
        if values.map(lambda v: bool(_URL_LIKE_RE.match(v))).any():
            return column
    return None


def _find_id_column(df: pd.DataFrame) -> str | None:
    for column in df.columns:
        if str(column).strip().lower() in _ID_COLUMN_NAMES:
            return column
    return None


def _is_valid_url(value: str) -> bool:
    try:
        _validate_url(value)
    except ValidationError:
        return False
    return True
