import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def html_fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR / "html"
