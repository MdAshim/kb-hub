from django.db import models
from django.utils import timezone


class HarvestJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_DONE, "Done"),
    ]

    original_filename = models.CharField(max_length=255)
    uploaded_file = models.FileField(upload_to="uploads/")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    total_urls = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.status})"


class UrlRecord(models.Model):
    STATUS_PENDING = "pending"
    STATUS_FETCHING = "fetching"
    STATUS_FETCHED = "fetched"
    STATUS_INDEXED = "indexed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_FETCHING, "Fetching"),
        (STATUS_FETCHED, "Fetched"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_FAILED, "Failed"),
    ]

    FETCH_METHOD_REQUESTS = "requests"
    FETCH_METHOD_PLAYWRIGHT = "playwright"
    FETCH_METHOD_CHOICES = [
        (FETCH_METHOD_REQUESTS, "requests"),
        (FETCH_METHOD_PLAYWRIGHT, "playwright"),
    ]

    job = models.ForeignKey(HarvestJob, on_delete=models.CASCADE, related_name="url_records")
    source_id = models.CharField(max_length=64, null=True, blank=True)
    url = models.URLField(max_length=2048)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    status_code = models.SmallIntegerField(null=True, blank=True)
    raw_html = models.TextField(blank=True)
    clean_text = models.TextField(blank=True)
    title = models.CharField(max_length=512, blank=True)
    fetch_method = models.CharField(max_length=16, choices=FETCH_METHOD_CHOICES, blank=True)
    error = models.TextField(blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("job", "url")

    def __str__(self) -> str:
        return f"{self.url} ({self.status})"


def update_job_status(job: HarvestJob) -> None:
    """Mark a job done once every one of its records has reached a terminal
    state (indexed or failed). Called from harvest.tasks.fetch_url (for
    records that fail before ingest) and knowledge.tasks.ingest_url (for
    records that reach indexed/failed). Lives here, not in harvest.tasks, so
    knowledge.tasks can import it without a harvest.tasks <-> knowledge.tasks
    circular import (fetch_url calls ingest_url directly)."""
    unfinished = job.url_records.filter(
        status__in=[UrlRecord.STATUS_PENDING, UrlRecord.STATUS_FETCHING, UrlRecord.STATUS_FETCHED]
    ).exists()
    if not unfinished and job.status != HarvestJob.STATUS_DONE:
        job.status = HarvestJob.STATUS_DONE
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
