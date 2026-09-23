"""DRF views for the read-only URL/job endpoints and the search endpoint."""

from __future__ import annotations

from django.http import Http404
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from harvest.models import HarvestJob, UrlRecord
from knowledge.vector_store import get_vector_store
from search.formatter import format_results
from search.retriever import retrieve

from .serializers import HarvestJobSerializer, SearchRequestSerializer, UrlRecordSerializer


class UrlRecordPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class UrlRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UrlRecordSerializer
    pagination_class = UrlRecordPagination

    def get_queryset(self):
        queryset = UrlRecord.objects.order_by("id")
        if self.action != "list":
            return queryset
        status_code = self.request.query_params.get("status_code")
        if status_code not in (None, ""):
            queryset = queryset.filter(status_code=status_code)
        job_id = self.request.query_params.get("job")
        if job_id not in (None, ""):
            queryset = queryset.filter(job_id=job_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["apply_query_params"] = self.action == "list"
        return context

    def get_object(self):
        # get_object_or_404's Http404 message ("No UrlRecord matches the
        # given query.") would otherwise leak through as DRF's `detail`,
        # instead of API.md's documented {"detail": "Not found."}.
        try:
            return super().get_object()
        except Http404 as exc:
            raise NotFound() from exc


class HarvestJobView(APIView):
    def get(self, request, pk):
        try:
            job = HarvestJob.objects.get(pk=pk)
        except HarvestJob.DoesNotExist as exc:
            raise NotFound() from exc
        return Response(HarvestJobSerializer(job).data)


class SearchAPIView(APIView):
    def post(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        top_k = serializer.validated_data["top_k"]

        if get_vector_store().count() == 0:
            return Response({"detail": "No content has been indexed yet."}, status=503)

        chunks = retrieve(query, k=top_k)
        result = format_results(query, chunks)

        return Response(
            {
                "query": result.query,
                "llm_ok": result.llm_ok,
                "answer": result.answer,
                "people": [
                    {
                        "name": p.name,
                        "role": p.role,
                        "company": p.company,
                        "summary": p.summary,
                        "source_url": p.source_url,
                    }
                    for p in result.people
                ],
                "sources": [
                    {
                        "chunk_id": c.chunk_id,
                        "kind": c.kind,
                        "score": c.score,
                        "url": c.url,
                        "text": c.text,
                    }
                    for c in result.chunks
                ],
            }
        )
