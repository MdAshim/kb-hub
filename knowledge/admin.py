from django.contrib import admin

from .models import Chunk, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "company", "url_record")
    list_filter = ("company",)
    search_fields = ("name", "role", "company")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "url_record", "chunk_index")
    list_filter = ("kind",)
