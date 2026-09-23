"""Background fetch task. One Huey task per URL."""

from django.utils import timezone
from huey.contrib.djhuey import task

from .fetcher import fetch
from .models import HarvestJob, UrlRecord


@task(retries=0)
def fetch_url(record_id: int) -> None:
    """Load UrlRecord, call fetch(), save fields, set status fetched|failed,
    update job counters.

    Phase 1 scope: does not enqueue ingest_url (knowledge app doesn't exist
    yet) and treats fetched/failed as the job's terminal states. Phase 2 must
    change this to enqueue ingest_url on success and wait for indexed/failed.
    """
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
    record.fetched_at = timezone.now()
    record.save()

    _update_job_status(job)


def _update_job_status(job: HarvestJob) -> None:
    unfinished = job.url_records.filter(
        status__in=[UrlRecord.STATUS_PENDING, UrlRecord.STATUS_FETCHING]
    ).exists()
    if not unfinished and job.status != HarvestJob.STATUS_DONE:
        job.status = HarvestJob.STATUS_DONE
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
