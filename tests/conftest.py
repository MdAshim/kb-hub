import pathlib
import zlib

import numpy as np
import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from search.llm import LLMError

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


class FakeEmbedder:
    """Deterministic, dependency-free stand-in for knowledge.embedder.Embedder.
    Same text always hashes to the same unit-norm vector; different text
    (almost certainly) doesn't -- good enough for exercising the ingest/
    retrieval plumbing without loading the real ~130MB model."""

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.EMBEDDING_DIM

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.array([self._vector(t) for t in texts], dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)

    def _vector(self, text: str) -> np.ndarray:
        seed = zlib.crc32(text.encode("utf-8"))
        rng = np.random.default_rng(seed)
        vector = rng.standard_normal(self.dim).astype(np.float32)
        return vector / np.linalg.norm(vector)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


class FakeLLM:
    """Stand-in for a search.llm.LLMClient. Returns a canned dict, or raises
    LLMError if configured to simulate a failure."""

    def __init__(self, response: dict | None = None, fail: bool = False):
        self.response = response
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, timeout: int | None = None) -> dict:
        self.calls.append((system, user))
        if self.fail:
            raise LLMError("fake LLM failure")
        return self.response if self.response is not None else {"people": []}


@pytest.fixture
def fake_llm():
    return FakeLLM
