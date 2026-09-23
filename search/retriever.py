"""Embed a query, search FAISS, and load the matching chunks from SQLite."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from knowledge.embedder import get_embedder
from knowledge.models import Chunk
from knowledge.vector_store import get_vector_store


@dataclass
class RetrievedChunk:
    chunk_id: int
    text: str
    kind: str
    score: float
    url: str


def retrieve(query: str, k: int | None = None) -> list[RetrievedChunk]:
    """Embed query, FAISS search k, load Chunks (select_related url, person),
    score += PERSON_BOOST for kind='person', sort desc, return.

    FAISS ids with no matching Chunk row (orphans, per DATABASE.md) are
    dropped implicitly: filter(id__in=ids) simply doesn't return them."""
    k = k if k is not None else settings.SEARCH_TOP_K

    vector = get_embedder().embed_query(query)
    hits = get_vector_store().search(vector, k)
    if not hits:
        return []

    scores = dict(hits)
    chunks = Chunk.objects.filter(id__in=scores.keys()).select_related("url_record", "person")

    results = [
        RetrievedChunk(
            chunk_id=chunk.id,
            text=chunk.text,
            kind=chunk.kind,
            score=scores[chunk.id] + (settings.PERSON_BOOST if chunk.kind == Chunk.KIND_PERSON else 0),
            url=chunk.url_record.url,
        )
        for chunk in chunks
    ]
    results.sort(key=lambda r: r.score, reverse=True)
    return results
