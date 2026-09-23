from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import UploadForm
from .models import HarvestJob, UrlRecord
from .parsers import InvalidFileError, parse_url_file
from .tasks import fetch_url


def upload_view(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["file"]
            try:
                parse_result = parse_url_file(uploaded)
            except InvalidFileError as exc:
                form.add_error("file", str(exc))
                return render(request, "upload.html", {"form": form})

            uploaded.seek(0)
            job = HarvestJob.objects.create(
                original_filename=uploaded.name,
                uploaded_file=uploaded,
                status=HarvestJob.STATUS_PENDING,
                total_urls=len(parse_result.urls),
                skipped_rows=parse_result.skipped,
            )
            UrlRecord.objects.bulk_create(
                UrlRecord(job=job, source_id=parsed.source_id, url=parsed.url)
                for parsed in parse_result.urls
            )
            record_ids = list(job.url_records.values_list("id", flat=True))
            if not record_ids:
                job.status = HarvestJob.STATUS_DONE
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "finished_at"])
            else:
                for record_id in record_ids:
                    fetch_url(record_id)
            return redirect("harvest:job_detail", job_id=job.id)
    else:
        form = UploadForm()
    return render(request, "upload.html", {"form": form})


def job_detail_view(request, job_id: int):
    job = get_object_or_404(HarvestJob, id=job_id)
    return render(request, "job_status.html", {"job": job, "records": _records(job)})


def job_rows_partial(request, job_id: int):
    job = get_object_or_404(HarvestJob, id=job_id)
    return render(request, "_job_rows.html", {"job": job, "records": _records(job)})


def job_list_view(request):
    jobs = HarvestJob.objects.order_by("-created_at")
    return render(request, "job_list.html", {"jobs": jobs})


def _records(job: HarvestJob):
    return job.url_records.order_by("id")
