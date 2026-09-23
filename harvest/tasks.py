"""Background fetch task. One Huey task per URL."""

import logging

from django.utils import timezone
from huey.contrib.djhuey import task

from knowledge.tasks import ingest_url

from .fetcher import fetch
from .models import HarvestJob, UrlRecord, update_job_status

logger = logging.getLogger(__name__)


@task(retries=0)
def fetch_url(record_id: int) -> None:
    """Load UrlRecord, call fetch(), save fields, set status fetched|failed,
    enqueue ingest_url on success, update job status."""
    try:
        record = UrlRecord.objects.select_related("job").get(id=record_id)
    except UrlRecord.DoesNotExist:
        logger.error("fetch_url: no UrlRecord with id=%s", record_id)
        return

    job = record.job
    logger.info("fetch_url starting: record_id=%s job_id=%s url=%s", record.id, job.id, record.url)
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
        logger.error(
            "fetch_url failed: record_id=%s job_id=%s url=%s error=%s",
            record.id, job.id, record.url, result.error,
        )
    else:
        record.status = UrlRecord.STATUS_FETCHED
        record.error = ""  # clear any stale error from a prior failed attempt
        logger.info(
            "fetch_url succeeded: record_id=%s job_id=%s method=%s status_code=%s",
            record.id, job.id, record.fetch_method, record.status_code,
        )
    record.fetched_at = timezone.now()
    record.save()

    if record.status == UrlRecord.STATUS_FETCHED:
        ingest_url(record.id)

    update_job_status(job)
