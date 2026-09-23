import pytest
from django.urls import reverse

from harvest.models import HarvestJob, UrlRecord


def _make_records(*, status_codes):
    job = HarvestJob.objects.create(
        original_filename="t.csv", status=HarvestJob.STATUS_DONE, total_urls=len(status_codes)
    )
    return [
        UrlRecord.objects.create(
            job=job,
            url=f"https://example.com/{i}",
            status=UrlRecord.STATUS_INDEXED,
            status_code=code,
            raw_html=f"<html>{i}</html>",
            clean_text=f"text {i}",
        )
        for i, code in enumerate(status_codes)
    ]


@pytest.mark.django_db
def test_list_urls_returns_paginated_results_with_core_fields(client):
    # TC-24: GET /api/urls/ -> 200, paginated, has url/status_code/raw_html.
    _make_records(status_codes=[200, 200, 404])

    response = client.get(reverse("api:urlrecord-list"))

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"count", "next", "previous", "results"}
    assert data["count"] == 3
    item = data["results"][0]
    assert "url" in item
    assert "status_code" in item
    assert "raw_html" in item


@pytest.mark.django_db
def test_list_urls_include_html_false_omits_raw_html(client):
    # TC-25: include_html=false -> raw_html absent.
    _make_records(status_codes=[200])

    response = client.get(reverse("api:urlrecord-list"), {"include_html": "false"})

    item = response.json()["results"][0]
    assert "raw_html" not in item
    assert "clean_text" not in item  # include_text defaults to false too


@pytest.mark.django_db
def test_list_urls_include_text_true_adds_clean_text(client):
    # TC-36
    _make_records(status_codes=[200])

    response = client.get(reverse("api:urlrecord-list"), {"include_text": "true"})

    item = response.json()["results"][0]
    assert item["clean_text"] == "text 0"


@pytest.mark.django_db
def test_list_urls_filters_by_status_code(client):
    # TC-26: status_code=200 filter -> only matching rows.
    _make_records(status_codes=[200, 200, 404])

    response = client.get(reverse("api:urlrecord-list"), {"status_code": 200})

    data = response.json()
    assert data["count"] == 2
    assert all(item["status_code"] == 200 for item in data["results"])


@pytest.mark.django_db
def test_list_urls_filters_by_job(client):
    # TC-37
    job_a = HarvestJob.objects.create(original_filename="a.csv", status=HarvestJob.STATUS_DONE, total_urls=1)
    job_b = HarvestJob.objects.create(original_filename="b.csv", status=HarvestJob.STATUS_DONE, total_urls=1)
    UrlRecord.objects.create(job=job_a, url="https://example.com/a", status_code=200)
    UrlRecord.objects.create(job=job_b, url="https://example.com/b", status_code=200)

    response = client.get(reverse("api:urlrecord-list"), {"job": job_a.id})

    data = response.json()
    assert data["count"] == 1
    assert data["results"][0]["url"] == "https://example.com/a"


@pytest.mark.django_db
def test_list_urls_page_size_param(client):
    # TC-38
    _make_records(status_codes=[200] * 5)

    response = client.get(reverse("api:urlrecord-list"), {"page_size": 2})

    data = response.json()
    assert len(data["results"]) == 2
    assert data["next"] is not None


@pytest.mark.django_db
def test_retrieve_url_returns_404_for_unknown_id(client):
    # TC-27: GET unknown id -> 404.
    response = client.get(reverse("api:urlrecord-detail", args=[999]))

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}


@pytest.mark.django_db
def test_retrieve_url_always_includes_raw_html_and_clean_text(client):
    # TC-39
    (record,) = _make_records(status_codes=[200])

    # Even with include_html=false, the detail endpoint always includes both.
    response = client.get(
        reverse("api:urlrecord-detail", args=[record.id]), {"include_html": "false"}
    )

    data = response.json()
    assert data["raw_html"] == "<html>0</html>"
    assert data["clean_text"] == "text 0"
