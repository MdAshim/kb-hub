import pathlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def html_fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR / "html"


@pytest.fixture
def files_fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR / "files"


@pytest.fixture
def upload_file():
    """Build a SimpleUploadedFile from a file under tests/fixtures/files/."""

    def _build(filename: str, content_type: str = "application/octet-stream") -> SimpleUploadedFile:
        path = FIXTURES_DIR / "files" / filename
        return SimpleUploadedFile(filename, path.read_bytes(), content_type=content_type)

    return _build
