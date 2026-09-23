"""Background fetch task. One Huey task per URL."""

from django.utils import timezone
from huey.contrib.djhuey import task

from knowledge.tasks import ingest_url

from .fetcher import fetch
from .models import HarvestJob, UrlRecord, update_job_status


@task(retries=0)
def fetch_url(record_id: int) -> None:
    """Load UrlRecord, call fetch(), save fields, set status fetched|failed,
    enqueue ingest_url on success, update job status."""
    try:
        record = UrlRecord.objects.select_related("job").get(id=record_id)
    except UrlRecord.DoesNotExist:
        return

    job = record.job
    if job.status == HarvestJob.STATUS_PENDING:
        job.status = HarvestJob.STATUS_RUNNING
        job.save(update_fields=["status"])

    record.status = UrlRecord.STATUS_FETCHING
    record.save(update_fields=["status"])

    result = fetch(record.url)

    record.status_code = result.status_code
    record.raw_html = result.html
    record.clean_text = result.text
    record.title = result.title
    record.fetch_method = result.method
    if result.error:
        record.status = UrlRecord.STATUS_FAILED
        record.error = result.error
    else:
        record.status = UrlRecord.STATUS_FETCHED
        record.error = ""  # clear any stale error from a prior failed attempt
    record.fetched_at = timezone.now()
    record.save()

    if record.status == UrlRecord.STATUS_FETCHED:
        ingest_url(record.id)

    update_job_status(job)
