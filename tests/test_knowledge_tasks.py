import pytest

from harvest.models import HarvestJob, UrlRecord
from knowledge import tasks
from knowledge.extractor import PersonData
from knowledge.models import Chunk, Person
from knowledge.vector_store import VectorStore


def _make_record(clean_text: str, title: str = "Acme") -> UrlRecord:
    job = HarvestJob.objects.create(
        original_filename="t.csv", status=HarvestJob.STATUS_RUNNING, total_urls=1
    )
    return UrlRecord.objects.create(
        job=job,
        url="https://example.com/a",
        status=UrlRecord.STATUS_FETCHED,
        clean_text=clean_text,
        title=title,
    )


@pytest.mark.django_db
def test_ingest_url_creates_chunks_with_matching_vector_count(monkeypatch, tmp_path, fake_embedder):
    # TC-14: ingest_url -> Chunks created; vector count = chunk count.
    record = _make_record("Jane Smith is the CEO of Acme. " * 30, title="Acme Leadership")
    store = VectorStore(path=tmp_path / "test.index", dim=fake_embedder.dim)
    monkeypatch.setattr(tasks, "get_embedder", lambda: fake_embedder)
    monkeypatch.setattr(tasks, "get_vector_store", lambda: store)
    monkeypatch.setattr(
        tasks,
        "extract_people",
        lambda text, company_hint: [
            PersonData(name="Jane Smith", role="CEO", company="Acme", bio="Leads it.")
        ],
    )

    tasks.ingest_url.call_local(record.id)

    record.refresh_from_db()
    assert record.status == UrlRecord.STATUS_INDEXED
    assert record.indexed_at is not None

    chunks = list(Chunk.objects.filter(url_record=record))
    assert len(chunks) >= 2  # at least one text chunk + the person chunk
    assert Chunk.objects.filter(url_record=record, kind=Chunk.KIND_PERSON).count() == 1
    assert Person.objects.filter(url_record=record, name="Jane Smith").exists()
    assert store._index.ntotal == len(chunks)

    record.job.refresh_from_db()
    assert record.job.status == HarvestJob.STATUS_DONE


@pytest.mark.django_db
def test_ingest_url_reingest_removes_old_vectors_no_duplicates(monkeypatch, tmp_path, fake_embedder):
    # TC-17: re-ingesting the same record removes old vectors/chunks first.
    record = _make_record("Jane Smith is the CEO of Acme. " * 30, title="Acme Leadership")
    store = VectorStore(path=tmp_path / "test.index", dim=fake_embedder.dim)
    monkeypatch.setattr(tasks, "get_embedder", lambda: fake_embedder)
    monkeypatch.setattr(tasks, "get_vector_store", lambda: store)
    monkeypatch.setattr(tasks, "extract_people", lambda text, company_hint: [])

    tasks.ingest_url.call_local(record.id)
    first_ids = set(Chunk.objects.filter(url_record=record).values_list("id", flat=True))
    assert store._index.ntotal == len(first_ids)

    tasks.ingest_url.call_local(record.id)
    second_ids = set(Chunk.objects.filter(url_record=record).values_list("id", flat=True))

    assert first_ids.isdisjoint(second_ids)  # old rows actually deleted, not left alongside
    assert store._index.ntotal == len(second_ids)


@pytest.mark.django_db
def test_ingest_url_keeps_text_chunks_when_extraction_fails(monkeypatch, tmp_path, fake_embedder):
    # Supports TC-16's other half ("text chunks still indexed"): even if
    # extract_people misbehaves and raises outright, ingest_url's own
    # defense-in-depth try/except must not lose the page's text chunks.
    record = _make_record("Some perfectly ordinary page text about a company.")
    store = VectorStore(path=tmp_path / "test.index", dim=fake_embedder.dim)
    monkeypatch.setattr(tasks, "get_embedder", lambda: fake_embedder)
    monkeypatch.setattr(tasks, "get_vector_store", lambda: store)

    def _raise(text, company_hint):
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks, "extract_people", _raise)

    tasks.ingest_url.call_local(record.id)

    record.refresh_from_db()
    assert record.status == UrlRecord.STATUS_INDEXED
    assert Chunk.objects.filter(url_record=record, kind=Chunk.KIND_TEXT).exists()
    assert not Person.objects.filter(url_record=record).exists()


@pytest.mark.django_db
def test_ingest_url_marks_failed_on_embedding_error(monkeypatch, tmp_path, fake_embedder):
    record = _make_record("Some page text.")
    store = VectorStore(path=tmp_path / "test.index", dim=fake_embedder.dim)
    monkeypatch.setattr(tasks, "get_vector_store", lambda: store)
    monkeypatch.setattr(tasks, "extract_people", lambda text, company_hint: [])

    class _BrokenEmbedder:
        def embed_documents(self, texts):
            raise RuntimeError("embedding backend down")

    monkeypatch.setattr(tasks, "get_embedder", lambda: _BrokenEmbedder())

    tasks.ingest_url.call_local(record.id)

    record.refresh_from_db()
    assert record.status == UrlRecord.STATUS_FAILED
    assert record.error
    assert store._index.ntotal == 0  # save() never called; no partial vectors
    # Chunk rows are still there per ADR-009 -- rebuild_index picks them up later.
    assert Chunk.objects.filter(url_record=record).exists()
