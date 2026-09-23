# API Design

Base path: `/api/`. JSON responses. No authentication (assignment scope).
Implemented with Django REST Framework.

## Summary
| Method | Path | Story | Purpose |
|---|---|---|---|
| GET | `/api/urls/` | US-13 | List harvested URLs (required by the brief) |
| GET | `/api/urls/{id}/` | US-14 | One harvested URL |
| GET | `/api/jobs/{id}/` | US-16 | Job progress |
| POST | `/api/search/` | US-15 | Semantic search with structured people |

## GET /api/urls/
Returns harvested URL information: URL, HTTP status code and raw HTML/content.

Query parameters:
| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Max 100 |
| `include_html` | bool | `true` | `false` omits `raw_html` |
| `include_text` | bool | `false` | `true` adds `clean_text` |
| `status_code` | int | | Filter by HTTP status |
| `job` | int | | Filter by job id |

Response `200`:
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "source_id": "1",
      "url": "https://www.apple.com/in/leadership/",
      "status_code": 200,
      "status": "indexed",
      "title": "Apple Leadership",
      "fetch_method": "requests",
      "fetched_at": "2026-09-24T10:15:02Z",
      "error": "",
      "raw_html": "<!DOCTYPE html><html>..."
    }
  ]
}
```
A failed fetch appears with `"status": "failed"`, `status_code` null or the error code, and `error` set.

## GET /api/urls/{id}/
Same object as a list item, always including `raw_html` and `clean_text`.
`404` if not found:
```json
{ "detail": "Not found." }
```

## GET /api/jobs/{id}/
```json
{
  "id": 3,
  "original_filename": "Leadership_URL.xlsx",
  "status": "running",
  "total_urls": 5,
  "skipped_rows": 0,
  "counts": { "pending": 0, "fetching": 1, "fetched": 1, "indexed": 2, "failed": 1 },
  "created_at": "2026-09-24T10:14:55Z",
  "finished_at": null
}
```

## POST /api/search/
Request:
```json
{ "query": "Who is the CFO of Oracle?", "top_k": 5 }
```
| Field | Rules |
|---|---|
| `query` | required, 3 to 500 chars |
| `top_k` | optional, 1 to 20, default 5 (number of people/chunks returned) |

Response `200`:
```json
{
  "query": "Who is the CFO of Oracle?",
  "llm_ok": true,
  "answer": "Oracle's CFO is ...",
  "people": [
    {
      "name": "...",
      "role": "Chief Financial Officer",
      "company": "Oracle",
      "summary": "...",
      "source_url": "https://www.oracle.com/in/corporate/executives/"
    }
  ],
  "sources": [
    { "chunk_id": 42, "kind": "person", "score": 0.83, "url": "https://www.oracle.com/in/corporate/executives/", "text": "..." }
  ]
}
```
When the LLM fails, `llm_ok` is `false`, `answer` is null, `people` is empty, and `sources` still holds the retrieved chunks.

`sources` always holds up to `top_k` chunks whenever the index is non-empty, even for a query
about something that was never fetched/ingested (e.g. a site the harvester couldn't reach):
FAISS's nearest-neighbor search has no relevance floor, so it returns the closest available
vectors regardless of whether they're actually relevant. `people` and `answer` are what express
"not found" in that case (an empty `people` list and an explicit not-found sentence), not an
empty `sources`.

## Errors
| Code | When | Body |
|---|---|---|
| 400 | Invalid query params or body | `{"field": ["message"]}` (DRF default) |
| 404 | Unknown id | `{"detail": "Not found."}` |
| 503 | Index empty on search | `{"detail": "No content has been indexed yet."}` |
| 500 | Unexpected | `{"detail": "Internal error."}` (details only in logs) |

## Examples
```bash
curl "http://127.0.0.1:8000/api/urls/?include_html=false"
curl "http://127.0.0.1:8000/api/urls/1/"
curl -X POST http://127.0.0.1:8000/api/search/ \
     -H "Content-Type: application/json" \
     -d '{"query": "Who leads Tesla?", "top_k": 5}'
```
