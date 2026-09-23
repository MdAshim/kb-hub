"""Process-wide singleton wrapper around the sentence-transformers embedding model."""

from __future__ import annotations

import numpy as np
from django.conf import settings
from sentence_transformers import SentenceTransformer

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    """Process-wide singleton (lazy load). bge query prefix applies to
    queries only -- bge is an asymmetric model, passages get no prefix."""

    def __init__(self) -> None:
        self.model_name = settings.EMBEDDING_MODEL
        self._model = SentenceTransformer(self.model_name)
        self.dim = self._model.get_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        vector = self._model.encode(
            QUERY_PREFIX + text, normalize_embeddings=True, convert_to_numpy=True
        )
        return np.asarray(vector, dtype=np.float32)


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
