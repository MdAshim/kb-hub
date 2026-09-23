import pytest

from harvest.parsers import InvalidFileError, parse_url_file


def test_parse_detects_link_column(upload_file):
    # TC-04: column named "Link" is detected as the URL column.
    result = parse_url_file(upload_file("link_column.csv", "text/csv"))
    assert [u.url for u in result.urls] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_parse_raises_without_url_column(upload_file):
    # TC-05: no URL-like column anywhere raises InvalidFileError.
    with pytest.raises(InvalidFileError):
        parse_url_file(upload_file("no_url_column.csv", "text/csv"))


def test_parse_dedupes_and_counts_skipped(upload_file):
    # TC-06: duplicates collapse to one record; blank/malformed rows are skipped and counted.
    result = parse_url_file(upload_file("bad_rows.csv", "text/csv"))
    assert [u.url for u in result.urls] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert result.skipped == 2

    dup_result = parse_url_file(upload_file("duplicates.csv", "text/csv"))
    assert [u.url for u in dup_result.urls] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert dup_result.skipped == 0


def test_parse_stores_source_id(upload_file):
    # TC-07: the ID column is stored as source_id.
    result = parse_url_file(upload_file("valid.csv", "text/csv"))
    assert [u.source_id for u in result.urls] == ["1", "2", "3"]


def test_parse_reads_xlsx(upload_file):
    # TC-54
    result = parse_url_file(
        upload_file(
            "valid.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    assert len(result.urls) == 5
    assert result.skipped == 0
