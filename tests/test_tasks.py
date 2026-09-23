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
    # ingest_url is knowledge's concern (see tests/test_knowledge_tasks.py);
    # stub it here so this stays a fetch-only test.
    ingest_calls = []
    monkeypatch.setattr(tasks, "ingest_url", lambda record_id: ingest_calls.append(record_id))

    tasks.fetch_url.call_local(record.id)

    record.refresh_from_db()
    assert record.status == UrlRecord.STATUS_FETCHED
    assert record.status_code == 200
    assert record.raw_html == "<html>hi</html>"
    assert record.clean_text == "hi"
    assert record.fetch_method == "requests"
    assert record.fetched_at is not None
    assert ingest_calls == [record.id]

    # fetched is no longer terminal as of Phase 2 -- the job isn't done until
    # ingest_url moves the record to indexed/failed.
    job.refresh_from_db()
    assert job.status == HarvestJob.STATUS_RUNNING


@pytest.mark.django_db
def test_fetch_url_clears_stale_error_on_success(monkeypatch):
    # TC-52 (paired with test_knowledge_tasks.py::test_ingest_url_clears_stale_error_on_success)
    # A record with a leftover error from a prior failed attempt must not
    # keep showing it once a later fetch succeeds.
    job = _make_job("https://example.com/a")
    record = job.url_records.get()
    record.error = "Connection refused"
    record.save(update_fields=["error"])

    monkeypatch.setattr(
        tasks,
        "fetch",
        lambda url: FetchResult(status_code=200, html="<html>hi</html>", text="hi", method="requests"),
    )
    monkeypatch.setattr(tasks, "ingest_url", lambda record_id: None)

    tasks.fetch_url.call_local(record.id)

    record.refresh_from_db()
    assert record.status == UrlRecord.STATUS_FETCHED
    assert record.error == ""


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
