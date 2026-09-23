"""FAISS wrapper. All FAISS access in the project goes through this module."""

from __future__ import annotations

import threading
from pathlib import Path

import faiss
import numpy as np
from django.conf import settings


class VectorStore:
    """Wraps faiss.IndexIDMap(faiss.IndexFlatIP(dim)). Loads from path if
    present. Writes guarded by a lock; save() after each add/remove batch."""

    def __init__(self, path: str | Path | None = None, dim: int | None = None) -> None:
        self.path = Path(path) if path is not None else Path(settings.FAISS_INDEX_PATH)
        self.dim = dim if dim is not None else settings.EMBEDDING_DIM
        self._lock = threading.Lock()
        self._index = self._load()

    def _load(self):
        if self.path.exists():
            return faiss.read_index(str(self.path))
        return faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        if not ids:
            return
        with self._lock:
            self._index.add_with_ids(
                np.asarray(vectors, dtype=np.float32), np.asarray(ids, dtype=np.int64)
            )

    def remove(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock:
            self._index.remove_ids(np.asarray(ids, dtype=np.int64))

    def search(self, vector: np.ndarray, k: int) -> list[tuple[int, float]]:
        with self._lock:
            distances, indices = self._index.search(
                np.asarray(vector, dtype=np.float32).reshape(1, -1), k
            )
        return [
            (int(idx), float(score))
            for idx, score in zip(indices[0], distances[0])
            if idx != -1
        ]

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self._index, str(self.path))

    def reset(self) -> None:
        with self._lock:
            self._index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
