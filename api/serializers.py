"""DRF serializers for the read-only URL/job endpoints and the search request."""

from __future__ import annotations

from django.db.models import Count
from rest_framework import serializers

from harvest.models import HarvestJob, UrlRecord


def _bool_param(request, name: str, default: bool) -> bool:
    value = request.query_params.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class UrlRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UrlRecord
        fields = [
            "id",
            "source_id",
            "url",
            "status_code",
            "status",
            "title",
            "fetch_method",
            "fetched_at",
            "error",
            "raw_html",
            "clean_text",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        # Only the list view opts into include_html/include_text toggling
        # (context["apply_query_params"]); the detail view always returns
        # raw_html and clean_text regardless of any query params present.
        if request is not None and self.context.get("apply_query_params"):
            if not _bool_param(request, "include_html", default=True):
                self.fields.pop("raw_html", None)
            if not _bool_param(request, "include_text", default=False):
                self.fields.pop("clean_text", None)


class HarvestJobSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()

    class Meta:
        model = HarvestJob
        fields = [
            "id",
            "original_filename",
            "status",
            "total_urls",
            "skipped_rows",
            "counts",
            "created_at",
            "finished_at",
        ]

    def get_counts(self, obj: HarvestJob) -> dict:
        counts = {choice: 0 for choice, _ in UrlRecord.STATUS_CHOICES}
        rows = obj.url_records.values("status").annotate(n=Count("status"))
        for row in rows:
            counts[row["status"]] = row["n"]
        return counts


class SearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(min_length=3, max_length=500)
    top_k = serializers.IntegerField(min_value=1, max_value=20, default=5)
