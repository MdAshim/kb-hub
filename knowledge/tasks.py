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
from .extractor import extract_people
from .models import Chunk, Person
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


@task()
def ingest_url(record_id: int) -> None:
    """1. Delete old Chunks/Persons for the record and remove their vectors.
    2. chunk_text -> Chunk(kind='text').
    3. extract_people -> Person + Chunk(kind='person', text='Name, Role, Company. Bio').
    4. Embed all new chunks, VectorStore.add(chunk ids), save.
    5. Set record status 'indexed'. On extractor failure, keep text chunks and log."""
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

    text_pieces = chunk_text(
        record.clean_text, record.title, settings.CHUNK_SIZE_TOKENS, settings.CHUNK_OVERLAP_TOKENS
    )
    Chunk.objects.bulk_create(
        Chunk(url_record=record, kind=Chunk.KIND_TEXT, chunk_index=i, text=piece)
        for i, piece in enumerate(text_pieces)
    )

    company_hint = record.title or urlparse(record.url).netloc
    try:
        people = extract_people(record.clean_text, company_hint)
    except Exception:
        logger.exception("extract_people raised unexpectedly for record %s", record.id)
        people = []

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
