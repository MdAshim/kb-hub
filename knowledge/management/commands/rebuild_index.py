"""Re-embed all chunks into a fresh FAISS index."""

from django.core.management.base import BaseCommand

from knowledge.embedder import get_embedder
from knowledge.models import Chunk
from knowledge.vector_store import get_vector_store

BATCH_SIZE = 256


class Command(BaseCommand):
    help = "Reset the FAISS index and re-embed every Chunk row from SQLite."

    def handle(self, *args, **options):
        vector_store = get_vector_store()
        vector_store.reset()
        embedder = get_embedder()

        total = 0
        batch: list[Chunk] = []
        for chunk in Chunk.objects.order_by("id").iterator(chunk_size=BATCH_SIZE):
            batch.append(chunk)
            if len(batch) >= BATCH_SIZE:
                total += self._embed_and_add(batch, embedder, vector_store)
                batch = []
        if batch:
            total += self._embed_and_add(batch, embedder, vector_store)

        vector_store.save()
        self.stdout.write(self.style.SUCCESS(f"Rebuilt index: {total} chunks embedded"))

    def _embed_and_add(self, batch: list[Chunk], embedder, vector_store) -> int:
        vectors = embedder.embed_documents([c.text for c in batch])
        vector_store.add([c.id for c in batch], vectors)
        return len(batch)
