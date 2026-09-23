import json
from types import SimpleNamespace

import pytest
from django.urls import reverse

from harvest.models import HarvestJob, UrlRecord
from knowledge.models import Chunk
from knowledge.vector_store import VectorStore
from search import retriever


@pytest.mark.django_db
def test_search_empty_query_returns_400(client):
    # TC-28: POST /api/search/ empty query -> 400.
    response = client.post(
        reverse("api:search"), data=json.dumps({"query": ""}), content_type="application/json"
    )

    assert response.status_code == 400
    assert "query" in response.json()


@pytest.mark.django_db
def test_search_missing_query_returns_400(client):
    # TC-33
    response = client.post(
        reverse("api:search"), data=json.dumps({}), content_type="application/json"
    )

    assert response.status_code == 400
    assert "query" in response.json()


@pytest.mark.django_db
def test_search_top_k_out_of_range_returns_400(client):
    # TC-34
    response = client.post(
        reverse("api:search"),
        data=json.dumps({"query": "who is the CEO?", "top_k": 50}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "top_k" in response.json()


@pytest.mark.django_db
def test_search_on_empty_index_returns_503(client):
    # TC-23 (API surface; the HTML-page half is test_search_view.py::test_search_empty_index_shows_message)
    response = client.post(
        reverse("api:search"),
        data=json.dumps({"query": "who is the CEO?"}),
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "No content has been indexed yet."}


@pytest.mark.django_db
def test_search_valid_query_returns_answer_people_and_sources(monkeypatch, client, fake_llm, tmp_path):
    # TC-29: POST /api/search/ valid -> 200 with answer/people/sources.
    job = HarvestJob.objects.create(
        original_filename="t.csv", status=HarvestJob.STATUS_DONE, total_urls=1
    )
    record = UrlRecord.objects.create(
        job=job, url="https://example.com/a", status=UrlRecord.STATUS_INDEXED
    )
    chunk = Chunk.objects.create(
        url_record=record, kind=Chunk.KIND_PERSON, chunk_index=0, text="Jane Smith, CEO, Acme."
    )

    store = VectorStore(path=tmp_path / "t.index", dim=8)
    store.add([chunk.id], [[0.1] * 8])
    monkeypatch.setattr(retriever, "get_vector_store", lambda: store)
    monkeypatch.setattr(retriever, "get_embedder", lambda: SimpleNamespace(embed_query=lambda q: [0.1] * 8))
    monkeypatch.setattr("api.views.get_vector_store", lambda: store)

    llm = fake_llm(
        response={
            "answer": "Jane Smith is the CEO.",
            "people": [
                {
                    "name": "Jane Smith",
                    "role": "CEO",
                    "company": "Acme",
                    "summary": "Leads Acme.",
                    "source_url": "https://example.com/a",
                }
            ],
        }
    )
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)

    response = client.post(
        reverse("api:search"),
        data=json.dumps({"query": "Who is the CEO?", "top_k": 5}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Who is the CEO?"
    assert data["llm_ok"] is True
    assert data["answer"] == "Jane Smith is the CEO."
    assert data["people"] == [
        {
            "name": "Jane Smith",
            "role": "CEO",
            "company": "Acme",
            "summary": "Leads Acme.",
            "source_url": "https://example.com/a",
        }
    ]
    assert len(data["sources"]) == 1
    source = data["sources"][0]
    assert source["chunk_id"] == chunk.id
    assert source["kind"] == "person"
    assert source["url"] == "https://example.com/a"
    assert source["text"] == "Jane Smith, CEO, Acme."


@pytest.mark.django_db
def test_search_llm_failure_returns_llm_ok_false_with_sources(monkeypatch, client, fake_llm, tmp_path):
    # TC-35
    job = HarvestJob.objects.create(
        original_filename="t.csv", status=HarvestJob.STATUS_DONE, total_urls=1
    )
    record = UrlRecord.objects.create(
        job=job, url="https://example.com/a", status=UrlRecord.STATUS_INDEXED
    )
    chunk = Chunk.objects.create(
        url_record=record, kind=Chunk.KIND_TEXT, chunk_index=0, text="Some text."
    )

    store = VectorStore(path=tmp_path / "t.index", dim=8)
    store.add([chunk.id], [[0.1] * 8])
    monkeypatch.setattr(retriever, "get_vector_store", lambda: store)
    monkeypatch.setattr(retriever, "get_embedder", lambda: SimpleNamespace(embed_query=lambda q: [0.1] * 8))
    monkeypatch.setattr("api.views.get_vector_store", lambda: store)
    monkeypatch.setattr("search.formatter.get_llm", lambda: fake_llm(fail=True))

    response = client.post(
        reverse("api:search"),
        data=json.dumps({"query": "Who is the CEO?"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["llm_ok"] is False
    assert data["answer"] is None
    assert data["people"] == []
    assert len(data["sources"]) == 1
