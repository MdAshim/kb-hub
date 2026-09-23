import pytest
from django.urls import reverse

from harvest.models import HarvestJob, UrlRecord


@pytest.mark.django_db
def test_job_detail_returns_counts_per_status(client):
    # TC-30: GET /api/jobs/{id}/ -> counts per status.
    job = HarvestJob.objects.create(
        original_filename="Leadership_URL.xlsx",
        status=HarvestJob.STATUS_RUNNING,
        total_urls=5,
        skipped_rows=0,
    )
    UrlRecord.objects.create(job=job, url="https://example.com/a", status=UrlRecord.STATUS_FETCHING)
    UrlRecord.objects.create(job=job, url="https://example.com/b", status=UrlRecord.STATUS_FETCHED)
    UrlRecord.objects.create(job=job, url="https://example.com/c", status=UrlRecord.STATUS_INDEXED)
    UrlRecord.objects.create(job=job, url="https://example.com/d", status=UrlRecord.STATUS_INDEXED)
    UrlRecord.objects.create(job=job, url="https://example.com/e", status=UrlRecord.STATUS_FAILED)

    response = client.get(reverse("api:job-detail", args=[job.id]))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job.id
    assert data["original_filename"] == "Leadership_URL.xlsx"
    assert data["status"] == "running"
    assert data["total_urls"] == 5
    assert data["skipped_rows"] == 0
    assert data["counts"] == {
        "pending": 0,
        "fetching": 1,
        "fetched": 1,
        "indexed": 2,
        "failed": 1,
    }
    assert data["finished_at"] is None


@pytest.mark.django_db
def test_job_detail_returns_404_for_unknown_id(client):
    # TC-32
    response = client.get(reverse("api:job-detail", args=[999]))

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}
