from django.shortcuts import render

from knowledge.vector_store import get_vector_store

from .formatter import format_results
from .retriever import retrieve

MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 500


def search_view(request):
    query = request.GET.get("q", "").strip()
    context = {"query": query}

    if query:
        if not (MIN_QUERY_LENGTH <= len(query) <= MAX_QUERY_LENGTH):
            context["error"] = (
                f"Query must be between {MIN_QUERY_LENGTH} and {MAX_QUERY_LENGTH} characters."
            )
        elif get_vector_store().count() == 0:
            context["empty_index"] = True
        else:
            chunks = retrieve(query)
            context["result"] = format_results(query, chunks)

    template = "_search_results.html" if request.headers.get("HX-Request") == "true" else "search.html"
    return render(request, template, context)
