import pytest

from harvest import tasks
from harvest.fetcher import FetchResult
from harvest.models import HarvestJob, UrlRecord


def _make_job(*urls: str) -> HarvestJob:
    job = HarvestJob.objects.create(
        original_filename="test.csv",
        status=HarvestJob.STATUS_PENDING,
        total_urls=len(urls),
        skipped_rows=0,
    )
    for url in urls:
        UrlRecord.objects.create(job=job, url=url)
    return job


@pytest.mark.django_db
def test_fetch_url_saves_fetched_fields(monkeypatch):
    # TC-08: a successful fetch persists status_code/raw_html/clean_text/method.
    job = _make_job("https://example.com/a")
    record = job.url_records.get()

    monkeypatch.setattr(
        tasks,
        "fetch",
        lambda url: FetchResult(
            status_code=200,
            html="<html>hi</html>",
            text="hi",
            title="Hi",
            method="requests",
        ),
    )

    tasks.fetch_url.call_local(record.id)

    record.refresh_from_db()
    assert record.status == UrlRecord.STATUS_FETCHED
    assert record.status_code == 200
    assert record.raw_html == "<html>hi</html>"
    assert record.clean_text == "hi"
    assert record.fetch_method == "requests"
    assert record.fetched_at is not None

    job.refresh_from_db()
    assert job.status == HarvestJob.STATUS_DONE
    assert job.finished_at is not None


@pytest.mark.django_db
def test_fetch_url_marks_failed_and_leaves_other_records_untouched(monkeypatch):
    # TC-11: a network-exception result marks the record failed without
    # touching sibling records or wrongly closing out the job.
    job = _make_job("https://example.com/a", "https://example.com/b")
    record_a, record_b = job.url_records.order_by("id")

    monkeypatch.setattr(
        tasks, "fetch", lambda url: FetchResult(error="Connection refused")
    )

    tasks.fetch_url.call_local(record_a.id)

    record_a.refresh_from_db()
    assert record_a.status == UrlRecord.STATUS_FAILED
    assert record_a.error == "Connection refused"

    record_b.refresh_from_db()
    assert record_b.status == UrlRecord.STATUS_PENDING

    job.refresh_from_db()
    assert job.status == HarvestJob.STATUS_RUNNING
