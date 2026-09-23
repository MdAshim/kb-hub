# Architecture Decision Records

Short records of significant choices. Add a new ADR when a decision changes.
Format: context, decision, consequences.

## ADR-001: Django + Django REST Framework
- **Context:** The brief prefers Django and DRF.
- **Decision:** Django 5 for web and ORM; DRF for the API.
- **Consequences:** Admin, forms, ORM and migrations for free; the API reuses the same models.

## ADR-002: FAISS instead of Milvus
- **Context:** Either is allowed. Scale is tens to hundreds of pages.
- **Decision:** FAISS `IndexIDMap(IndexFlatIP)` persisted to a file.
- **Consequences:** No Docker or extra service; exact search is fast at this size. No built-in
  metadata filtering, so metadata stays in SQLite. Milvus would be the upgrade path for scale.

## ADR-003: Huey with SQLite broker for background jobs
- **Context:** Scraping in the request would time out; Celery needs Redis/RabbitMQ.
- **Decision:** Huey `SqliteHuey`.
- **Consequences:** One extra command (`run_huey`), no extra infrastructure. Limited throughput,
  which is fine here.

## ADR-004: requests first, Playwright as fallback
- **Context:** Some target sites block plain HTTP clients or render content with JavaScript.
- **Decision:** Try requests + trafilatura; fall back to headless Chromium on 403/429 or short text.
- **Consequences:** Fast for simple pages, robust for hard ones. Requires `playwright install chromium`.

## ADR-005: bge-small-en-v1.5 embeddings
- **Context:** Need free, local, CPU-friendly embeddings with good retrieval quality.
- **Decision:** `BAAI/bge-small-en-v1.5` (384-dim) via sentence-transformers, normalized.
- **Consequences:** Small download, fast on CPU. Queries use the bge instruction prefix.
  Model name is configurable; changing it requires `rebuild_index`.

## ADR-006: Person cards alongside text chunks
- **Context:** The brief asks for person-related retrieval and prefers chunk-based or structured retrieval.
  Plain chunks often separate a name from its title.
- **Decision:** At ingest, the LLM extracts people into a Person table, and each person gets its
  own embedded "card" chunk. Retrieval boosts person chunks.
- **Consequences:** Much better answers for "who is X" queries; structured data is queryable in
  SQLite. Costs one LLM call per page at ingest; if extraction fails, text chunks still work.

## ADR-007: Local LLM via Ollama, pluggable client
- **Context:** The brief allows a local LLM or free APIs. A local model means no API key,
  no rate limits and no data leaving the machine.
- **Decision:** One `LLMClient` interface. Ollama is the default (`llama3.2:3b`, upgradeable to
  `llama3.1:8b`); Groq is an optional fallback via `LLM_PROVIDER=groq`.
- **Consequences:** Works fully offline after setup. Slower on CPU, so timeouts are 60 s and
  extraction runs in the background worker. Reviewers can switch providers without code changes. All prompts require JSON and context-only answers,
  with a raw-chunk fallback when the LLM fails.

## ADR-008: Server-rendered UI with HTMX
- **Context:** The UI needs upload, progress and search, nothing more.
- **Decision:** Django templates plus HTMX for polling and partial updates.
- **Consequences:** No frontend build step; one codebase. Less suited to a rich SPA, which is not needed.

## ADR-009: SQLite is the source of truth
- **Context:** Vector indexes can be lost or need re-embedding.
- **Decision:** All text lives in SQLite; FAISS stores vectors keyed by `Chunk.id` only.
- **Consequences:** The index can always be rebuilt with one command.
