from types import SimpleNamespace

import pytest
from django.urls import reverse

from harvest.models import HarvestJob, UrlRecord
from knowledge.models import Chunk
from knowledge.vector_store import VectorStore
from search import retriever


@pytest.mark.django_db
def test_search_empty_index_shows_message(client):
    # TC-23: search on an empty index shows "Nothing indexed yet".
    response = client.get(reverse("search:search"), {"q": "who is the CEO?"})

    assert response.status_code == 200
    assert "Nothing indexed yet" in response.content.decode()


@pytest.mark.django_db
def test_search_validates_short_query(client):
    # TC-57
    response = client.get(reverse("search:search"), {"q": "ab"})

    assert response.status_code == 200
    assert "between 3 and 500 characters" in response.content.decode()


@pytest.mark.django_db
def test_search_no_query_renders_empty_results(client):
    # TC-58
    response = client.get(reverse("search:search"))

    assert response.status_code == 200
    assert "Nothing indexed yet" not in response.content.decode()


@pytest.mark.django_db
def test_search_htmx_request_returns_partial_only(client):
    # TC-59
    response = client.get(
        reverse("search:search"), {"q": "who is the CEO?"}, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Nothing indexed yet" in content
    assert "<nav>" not in content  # partial, not the full page


@pytest.mark.django_db
def test_search_renders_person_card_on_success(client, monkeypatch, fake_llm, tmp_path):
    # TC-60
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
    monkeypatch.setattr("search.views.get_vector_store", lambda: store)

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

    response = client.get(reverse("search:search"), {"q": "who is the CEO?"})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Jane Smith" in content
    assert "Acme" in content
