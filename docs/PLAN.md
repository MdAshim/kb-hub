# Build Plan

Work top to bottom. Tick a box when the task is done and its tests pass.
Story IDs refer to `BACKLOG.md`.

## Phase 0: Project setup
- [x] Create Django project `config` and apps `harvest`, `knowledge`, `search`, `api`
- [x] Settings read from `.env` (python-dotenv); `data/` created on startup
- [x] Configure `SqliteHuey` at `data/huey.db`
- [x] Configure pytest-django; add `tests/fixtures/html/`
- [x] Base template with nav (Upload, Jobs, Search) and HTMX

## Phase 1: Upload and harvest (E1)
- [x] `HarvestJob`, `UrlRecord` models + migrations [US-01, US-05]
- [x] `parsers.parse_url_file()` for CSV and XLSX, column detection, validation, dedupe [US-02]
- [x] Upload form and view with type/size validation [US-01]
- [x] `fetcher.fetch()` with requests: UA, timeout, retries; trafilatura clean text [US-03]
- [x] Playwright fallback on 403/429 or short text [US-04]
- [x] Huey task `fetch_url(record_id)`; enqueue one per URL on upload [US-03]
- [x] Job status page with HTMX polling [US-06]
- [x] Run against `samples/Leadership_URL.xlsx`; save fetched HTML as test fixtures

## Phase 2: Knowledge base pipeline (E2)
- [x] `Person`, `Chunk` models + migrations [US-07, US-08]
- [x] `chunker.chunk_text()` with overlap and title prefix [US-07]
- [x] `embedder.Embedder` (singleton, batch, normalized) [US-07]
- [x] `vector_store.VectorStore`: load/save, add, remove, search, lock [US-07, US-09]
- [x] Install Ollama and pull `OLLAMA_MODEL` (see `LOCAL_SETUP.md`); pre-download embedding model
- [x] `search/llm.py`: `OllamaClient` (default, /api/chat, format=json, 60 s timeout) and optional `GroqClient` [US-08]
- [x] `extractor.extract_people()` with defensive JSON parsing [US-08]
- [x] Huey task `ingest_url(record_id)`, chained after a successful fetch [US-07]
- [x] Re-ingest removes old chunks and vectors [US-09]
- [x] `rebuild_index` management command [US-09]

## Phase 3: Search (E3)
- [ ] `retriever.retrieve()` with person boost [US-10]
- [ ] `formatter.format_results()` LLM prompt -> `{answer, people[]}` [US-11]
- [ ] Fallback to raw chunks on LLM failure; empty-index message [US-12]
- [ ] Search page: form, answer, person cards, collapsible sources [US-10, US-11]

## Phase 4: REST API (E4)
- [ ] `UrlRecordSerializer` with `include_html` toggle [US-13]
- [ ] `GET /api/urls/` with pagination and filters [US-13]
- [ ] `GET /api/urls/{id}/` [US-14]
- [ ] `POST /api/search/` [US-15]
- [ ] `GET /api/jobs/{id}/` [US-16]

## Phase 5: Quality and delivery (E5)
- [ ] Complete test cases in `TESTING.md` [US-18]
- [ ] Logging config; friendly error pages [US-19]
- [ ] README screenshots and sample queries [US-17]
- [ ] Update docs if the implementation diverged
- [ ] Fresh-clone test: follow README from scratch on a clean venv
