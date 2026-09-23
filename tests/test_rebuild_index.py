import pytest
from django.core.management import call_command

from harvest.models import HarvestJob, UrlRecord
from knowledge.management.commands import rebuild_index as rebuild_index_cmd
from knowledge.models import Chunk
from knowledge.vector_store import VectorStore


@pytest.mark.django_db
def test_rebuild_index_matches_chunk_count(monkeypatch, tmp_path, fake_embedder):
    # TC-18: rebuild_index -> index count equals Chunk count.
    job = HarvestJob.objects.create(
        original_filename="t.csv", status=HarvestJob.STATUS_DONE, total_urls=1
    )
    record = UrlRecord.objects.create(
        job=job, url="https://example.com/a", status=UrlRecord.STATUS_INDEXED
    )
    Chunk.objects.bulk_create(
        Chunk(url_record=record, kind=Chunk.KIND_TEXT, chunk_index=i, text=f"chunk {i} text")
        for i in range(300)  # > BATCH_SIZE (256), exercises the batching loop
    )

    store = VectorStore(path=tmp_path / "test.index", dim=fake_embedder.dim)
    monkeypatch.setattr(rebuild_index_cmd, "get_embedder", lambda: fake_embedder)
    monkeypatch.setattr(rebuild_index_cmd, "get_vector_store", lambda: store)

    call_command("rebuild_index")

    assert Chunk.objects.count() == 300
    assert store._index.ntotal == 300
