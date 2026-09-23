"""Ingest a fetched page: chunk, extract people, embed, index."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone
from huey.contrib.djhuey import task

from harvest.models import UrlRecord, update_job_status

from .chunker import chunk_text
from .embedder import get_embedder
from .extractor import PersonData, extract_people
from .models import Chunk, Person
from .structured_data import extract_json_ld_people
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


@task()
def ingest_url(record_id: int) -> None:
    """1. Delete old Chunks/Persons for the record and remove their vectors.
    2. Parse raw_html for schema.org Person entries in JSON-LD (cheap,
       deterministic, no LLM call -- see ADR-010).
    3. chunk_text -> Chunk(kind='text').
    4. extract_people -> Person + Chunk(kind='person', text='Name, Role, Company. Bio'),
       merged with the JSON-LD people (deduped by lowercased name, JSON-LD wins).
    5. Embed all new chunks, VectorStore.add(chunk ids), save.
    6. Set record status 'indexed'. On extractor failure, keep text chunks and log."""
    try:
        record = UrlRecord.objects.select_related("job").get(id=record_id)
    except UrlRecord.DoesNotExist:
        return

    vector_store = get_vector_store()
    old_chunk_ids = list(Chunk.objects.filter(url_record=record).values_list("id", flat=True))
    if old_chunk_ids:
        vector_store.remove(old_chunk_ids)
    Chunk.objects.filter(url_record=record).delete()
    Person.objects.filter(url_record=record).delete()

    try:
        json_ld_people = extract_json_ld_people(record.raw_html)
    except Exception:
        logger.exception("extract_json_ld_people raised unexpectedly for record %s", record.id)
        json_ld_people = []

    text_pieces = chunk_text(
        record.clean_text, record.title, settings.CHUNK_SIZE_TOKENS, settings.CHUNK_OVERLAP_TOKENS
    )
    Chunk.objects.bulk_create(
        Chunk(url_record=record, kind=Chunk.KIND_TEXT, chunk_index=i, text=piece)
        for i, piece in enumerate(text_pieces)
    )

    company_hint = record.title or urlparse(record.url).netloc
    try:
        llm_people = extract_people(record.clean_text, company_hint)
    except Exception:
        logger.exception("extract_people raised unexpectedly for record %s", record.id)
        llm_people = []

    people: list[PersonData] = list(json_ld_people)
    seen_names = {p.name.lower() for p in people}
    for person_data in llm_people:
        if person_data.name.lower() not in seen_names:
            people.append(person_data)
            seen_names.add(person_data.name.lower())

    for offset, person_data in enumerate(people):
        person = Person.objects.create(
            url_record=record,
            name=person_data.name,
            role=person_data.role,
            company=person_data.company,
            bio=person_data.bio,
        )
        card_text = f"{person.name}, {person.role}, {person.company}. {person.bio}".strip()
        Chunk.objects.create(
            url_record=record,
            person=person,
            kind=Chunk.KIND_PERSON,
            chunk_index=len(text_pieces) + offset,
            text=card_text,
        )

    all_chunks = list(Chunk.objects.filter(url_record=record).order_by("id"))
    if not all_chunks:
        record.status = UrlRecord.STATUS_INDEXED
        record.indexed_at = timezone.now()
        record.save(update_fields=["status", "indexed_at"])
        update_job_status(record.job)
        return

    try:
        embedder = get_embedder()
        vectors = embedder.embed_documents([c.text for c in all_chunks])
        vector_store.add([c.id for c in all_chunks], vectors)
        vector_store.save()
    except Exception as exc:
        logger.exception("Embedding/FAISS failure for record %s", record.id)
        record.status = UrlRecord.STATUS_FAILED
        record.error = str(exc)
        record.save(update_fields=["status", "error"])
        update_job_status(record.job)
        return

    record.status = UrlRecord.STATUS_INDEXED
    record.indexed_at = timezone.now()
    record.save(update_fields=["status", "indexed_at"])
    update_job_status(record.job)
