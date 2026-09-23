from types import SimpleNamespace

import pytest

from harvest.models import HarvestJob, UrlRecord
from knowledge.models import Chunk
from search import retriever


class _StubVectorStore:
    def __init__(self, hits):
        self._hits = hits

    def search(self, vector, k):
        return self._hits


def _make_record() -> UrlRecord:
    job = HarvestJob.objects.create(
        original_filename="t.csv", status=HarvestJob.STATUS_DONE, total_urls=1
    )
    return UrlRecord.objects.create(
        job=job, url="https://example.com/a", status=UrlRecord.STATUS_INDEXED
    )


@pytest.mark.django_db
def test_person_chunk_ranks_above_equal_score_text_chunk(monkeypatch):
    # TC-20: person boost causes a person chunk to outrank an equal-score
    # text chunk, isolated from any embedding model via a stubbed FAISS hit
    # list with identical raw scores (text chunk listed first).
    record = _make_record()
    text_chunk = Chunk.objects.create(
        url_record=record, kind=Chunk.KIND_TEXT, chunk_index=0, text="Some text."
    )
    person_chunk = Chunk.objects.create(
        url_record=record, kind=Chunk.KIND_PERSON, chunk_index=1, text="Jane Smith, CEO, Acme."
    )

    stub = _StubVectorStore([(text_chunk.id, 0.5), (person_chunk.id, 0.5)])
    monkeypatch.setattr(retriever, "get_vector_store", lambda: stub)
    monkeypatch.setattr(retriever, "get_embedder", lambda: SimpleNamespace(embed_query=lambda q: None))

    results = retriever.retrieve("who is the CEO?", k=2)

    assert [r.chunk_id for r in results] == [person_chunk.id, text_chunk.id]
    assert results[0].score > results[1].score


@pytest.mark.django_db
def test_retrieve_ignores_orphan_faiss_ids(monkeypatch):
    # TC-55
    record = _make_record()
    real_chunk = Chunk.objects.create(
        url_record=record, kind=Chunk.KIND_TEXT, chunk_index=0, text="Real chunk."
    )
    orphan_id = real_chunk.id + 999  # no Chunk row for this id

    stub = _StubVectorStore([(real_chunk.id, 0.8), (orphan_id, 0.9)])
    monkeypatch.setattr(retriever, "get_vector_store", lambda: stub)
    monkeypatch.setattr(retriever, "get_embedder", lambda: SimpleNamespace(embed_query=lambda q: None))

    results = retriever.retrieve("query", k=2)

    assert [r.chunk_id for r in results] == [real_chunk.id]


@pytest.mark.django_db
def test_retrieve_returns_empty_list_when_no_hits(monkeypatch):
    # TC-56
    stub = _StubVectorStore([])
    monkeypatch.setattr(retriever, "get_vector_store", lambda: stub)
    monkeypatch.setattr(retriever, "get_embedder", lambda: SimpleNamespace(embed_query=lambda q: None))

    assert retriever.retrieve("query") == []


@pytest.mark.django_db
@pytest.mark.slow
def test_retrieve_finds_relevant_chunk_in_top_three(monkeypatch, tmp_path):
    # TC-19: a genuinely relevant chunk ranks in the top 3 for a relevant
    # query. Needs the real embedding model -- FakeEmbedder's hash-based
    # vectors have no semantic similarity structure to test against.
    from knowledge.embedder import Embedder
    from knowledge.vector_store import VectorStore

    record = _make_record()
    relevant = Chunk.objects.create(
        url_record=record,
        kind=Chunk.KIND_PERSON,
        chunk_index=0,
        text="Jane Smith, Chief Executive Officer, Acme Corp. Leads the company's overall strategy.",
    )
    distractors = [
        Chunk.objects.create(
            url_record=record, kind=Chunk.KIND_TEXT, chunk_index=i, text=text
        )
        for i, text in enumerate(
            [
                "The weather today is sunny with a light breeze from the north.",
                "Our office is located downtown near the train station.",
                "The recipe calls for two cups of flour and a pinch of salt.",
            ],
            start=1,
        )
    ]

    embedder = Embedder()
    store = VectorStore(path=tmp_path / "test.index", dim=embedder.dim)
    all_chunks = [relevant] + distractors
    vectors = embedder.embed_documents([c.text for c in all_chunks])
    store.add([c.id for c in all_chunks], vectors)

    monkeypatch.setattr(retriever, "get_embedder", lambda: embedder)
    monkeypatch.setattr(retriever, "get_vector_store", lambda: store)

    results = retriever.retrieve("Who is the CEO of the company?", k=3)

    assert relevant.id in [r.chunk_id for r in results[:3]]
