import pytest
from django.urls import reverse

from harvest.models import HarvestJob, UrlRecord


@pytest.mark.django_db
def test_upload_valid_xlsx_creates_job_and_redirects(client, upload_file):
    # TC-01: a valid xlsx upload creates a HarvestJob and redirects to its page.
    response = client.post(
        reverse("harvest:upload"),
        {
            "file": upload_file(
                "valid.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    job = HarvestJob.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("harvest:job_detail", args=[job.id])
    assert job.total_urls == 5
    assert job.url_records.count() == 5


@pytest.mark.django_db
def test_job_rows_partial_shows_status_rows(client):
    # TC-12: the job rows partial lists each URL with its status.
    job = HarvestJob.objects.create(
        original_filename="test.csv",
        status=HarvestJob.STATUS_RUNNING,
        total_urls=2,
        skipped_rows=0,
    )
    UrlRecord.objects.create(job=job, url="https://example.com/a", status=UrlRecord.STATUS_FETCHED)
    UrlRecord.objects.create(job=job, url="https://example.com/b", status=UrlRecord.STATUS_PENDING)

    response = client.get(reverse("harvest:job_rows", args=[job.id]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "https://example.com/a" in content
    assert "https://example.com/b" in content
    assert "fetched" in content
    assert "pending" in content
