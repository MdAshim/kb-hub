from django.db import models

from harvest.models import UrlRecord


class Person(models.Model):
    url_record = models.ForeignKey(UrlRecord, on_delete=models.CASCADE, related_name="people")
    name = models.CharField(max_length=255, db_index=True)
    role = models.CharField(max_length=255)
    company = models.CharField(max_length=255, db_index=True)
    bio = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"


class Chunk(models.Model):
    KIND_TEXT = "text"
    KIND_PERSON = "person"
    KIND_CHOICES = [
        (KIND_TEXT, "Text"),
        (KIND_PERSON, "Person"),
    ]

    url_record = models.ForeignKey(UrlRecord, on_delete=models.CASCADE, related_name="chunks")
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="chunks")
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, db_index=True)
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Chunk {self.id} ({self.kind}) of UrlRecord {self.url_record_id}"
