"""Turn retrieved chunks into an LLM-written answer plus structured people."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings

from .llm import get_llm
from .retriever import RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Answer the user's question about people, using only the provided context. "
    'Return JSON only: {"answer":"","people":[{"name":"","role":"","company":"",'
    '"summary":"","source_url":""}]}. '
    '"answer" must always be a non-empty sentence: either a direct answer to the '
    "question drawn from the context, or an explicit statement that the context "
    "doesn't contain that information -- for example \"I don't have information "
    "about Oracle's CFO in the retrieved content.\" or \"The provided context "
    'doesn\'t mention a CEO of Microsoft.\" Never leave "answer" blank. '
    'Only include people in "people" who are directly relevant to answering the '
    "question, not everyone mentioned in the context. If no one in the context "
    'answers the question, return an empty "people" list. Cite each included '
    "person's source_url from the context."
)


@dataclass
class PersonResult:
    name: str
    role: str
    company: str
    summary: str
    source_url: str


@dataclass
class SearchResult:
    query: str
    llm_ok: bool
    answer: str | None
    people: list[PersonResult] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)


def format_results(query: str, chunks: list[RetrievedChunk]) -> SearchResult:
    """Build numbered context from the top SEARCH_CONTEXT_CHUNKS, each with
    its source URL. Ask LLM for {"answer": str, "people": [...]}. Validate;
    on any failure return SearchResult(llm_ok=False, chunks=chunks) -- chunks
    is always the full retrieved list passed in, not just the context slice,
    both on success and on failure."""
    context_chunks = chunks[: settings.SEARCH_CONTEXT_CHUNKS]
    context_block = "\n\n".join(
        f"[{i + 1}] (source: {c.url})\n{c.text}" for i, c in enumerate(context_chunks)
    )
    user = f"{context_block}\n\nQuestion: {query}" if context_block else f"Question: {query}"

    try:
        data = get_llm().complete_json(system=SYSTEM_PROMPT, user=user)
    except Exception:
        logger.exception("format_results: LLM call failed")
        return SearchResult(query=query, llm_ok=False, answer=None, people=[], chunks=chunks)

    result = _validate(query, data, chunks)
    if result is None:
        logger.error("format_results: LLM response failed validation: %r", data)
        return SearchResult(query=query, llm_ok=False, answer=None, people=[], chunks=chunks)
    return result


def _validate(query: str, data, chunks: list[RetrievedChunk]) -> SearchResult | None:
    if not isinstance(data, dict):
        return None
    answer = data.get("answer")
    people_raw = data.get("people")
    # An empty/whitespace-only answer is treated the same as a missing one:
    # don't rely on the model always following the "never leave answer blank"
    # instruction -- fall back to the raw-chunks view instead of showing a
    # blank answer box.
    if not isinstance(answer, str) or not answer.strip():
        return None
    if not isinstance(people_raw, list):
        return None

    people: list[PersonResult] = []
    for item in people_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        people.append(
            PersonResult(
                name=name,
                role=str(item.get("role", "")).strip(),
                company=str(item.get("company", "")).strip(),
                summary=str(item.get("summary", "")).strip(),
                source_url=str(item.get("source_url", "")).strip(),
            )
        )

    return SearchResult(query=query, llm_ok=True, answer=answer.strip(), people=people, chunks=chunks)
