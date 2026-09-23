from django.contrib import admin

from .models import HarvestJob, UrlRecord


@admin.register(HarvestJob)
class HarvestJobAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "status", "total_urls", "skipped_rows", "created_at", "finished_at")
    list_filter = ("status",)


@admin.register(UrlRecord)
class UrlRecordAdmin(admin.ModelAdmin):
    list_display = ("url", "job", "status", "status_code", "fetch_method", "fetched_at")
    list_filter = ("status", "fetch_method")
    search_fields = ("url", "title", "source_id")
