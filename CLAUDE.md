# CLAUDE.md

## Project
Knowledge Base Hub: a Django app that takes an uploaded CSV/XLSX of URLs, scrapes each page,
stores raw content in SQLite, embeds it into FAISS, and answers natural-language questions
about the people (executives, roles, bios) on those pages. Also exposes `GET /api/urls/`.

This is a take-home assignment. Clarity, working code and a clean README matter more than
extra features. Do not add features outside `docs/BACKLOG.md` without asking.

## Stack
- Python 3.11, Django 5, Django REST Framework
- Background jobs: Huey with `SqliteHuey` (no Redis, no Celery)
- Scraping: `requests` + `trafilatura` first; Playwright (Chromium) as fallback
- Embeddings: `sentence-transformers`, model `BAAI/bge-small-en-v1.5` (384-dim)
- Vector store: FAISS `IndexIDMap(IndexFlatIP)` on L2-normalized vectors, saved to `data/faiss.index`
- LLM: local Ollama by default (`llama3.2:3b`), Groq free tier as optional fallback; chosen via `LLM_PROVIDER`
- UI: Django templates + HTMX. No React, no separate frontend build.

## Commands
Prerequisite: Ollama installed and running with the model from `.env` pulled
(`ollama pull llama3.2:3b`). See `docs/LOCAL_SETUP.md`.
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
python manage.py migrate
python manage.py runserver          # web app
python manage.py run_huey           # background worker (separate terminal)
pytest                              # tests
python manage.py rebuild_index      # re-embed all chunks into a fresh FAISS index
ruff check .                        # lint
```

## Layout
```
config/       settings, root urls, huey config
harvest/      HarvestJob, UrlRecord models; upload view; parsers.py; fetcher.py; tasks.py
knowledge/    Person, Chunk models; chunker.py; embedder.py; vector_store.py; extractor.py; tasks.py
search/       retriever.py; llm.py; formatter.py; views.py
api/          serializers.py; views.py; urls.py
templates/    base, upload, job_status, search
samples/      Leadership_URL.xlsx (sample input from the assignment)
data/         db.sqlite3, faiss.index, huey.db  (gitignored)
docs/         design documents (see below)
tests/        pytest tests + fixtures/html/ (saved pages)
```

## Which doc governs what
Read the relevant doc before changing that area, and update it if the change alters the design.
- Requirements, story IDs (US-xx), acceptance criteria -> `docs/BACKLOG.md`
- Current task list -> `docs/PLAN.md` (tick checkboxes when done)
- System overview -> `docs/HLD.md`
- Module interfaces, function signatures -> `docs/LLD.md`
- Models, fields, FAISS id mapping -> `docs/DATABASE.md`
- Endpoints and JSON shapes -> `docs/API.md`
- Sequence and state diagrams -> `docs/WORKFLOWS.md`
- Test cases (TC-xx) -> `docs/TESTING.md`
- Design trade-offs -> `docs/DECISIONS.md` (add an ADR for any new significant choice)
- Local model install (Ollama, embedding model) -> `docs/LOCAL_SETUP.md`

## Data flow
upload -> parse file -> UrlRecord rows -> Huey fetch task per URL -> save status_code, raw_html,
clean_text -> ingest task: chunk text + LLM-extract Person rows -> build person-card chunks ->
embed -> FAISS add_with_ids(Chunk.id) -> search: embed query -> FAISS top-k -> load Chunks from
SQLite -> boost kind="person" -> LLM formats JSON -> result cards.

## Rules
- `Chunk.id` is the FAISS id. Never store text in FAISS; always resolve ids back through SQLite.
- All FAISS access goes through `knowledge/vector_store.py`. Writes are serialized (one worker or a lock).
- All LLM calls go through `search/llm.py`. Never call Groq/Ollama SDKs directly elsewhere.
- OllamaClient uses `POST {OLLAMA_BASE_URL}/api/chat` with `format="json"`, `stream=false`,
  timeout `LLM_TIMEOUT_SECONDS` (60 s default, local models are slow on CPU).
  If Ollama is unreachable, raise LLMError with a message telling the user to run `ollama serve`.
- LLM prompts must demand JSON only and must say "use only the provided context".
  Always parse defensively and fall back to showing raw chunks if parsing fails.
- Embedding model name and dimension live in settings, not hard-coded.
- The file parser must accept both `.csv` and `.xlsx` and find the URL column case-insensitively.
- Fetching: real browser User-Agent, timeout, retries. Fall back to Playwright on 403/429 or when
  extracted text is under ~500 chars. Record which method was used in `fetch_method`.
- Never crash a whole job because one URL failed; store the error on that `UrlRecord`.
- Secrets come from `.env` (see `.env.example`). Never commit keys or anything in `data/`.
- Tests must not hit the network or a real LLM: use saved HTML fixtures and a fake LLM client.

## Conventions
- Type hints on public functions; short docstrings.
- Keep views thin; logic lives in service/task modules.
- Add or update a test for every parser, chunker, retriever or serializer change.
- Reference story IDs in commit messages, e.g. `feat(harvest): playwright fallback [US-04]`.

## Workflow
Work phase by phase from `docs/PLAN.md`. Before coding a task, restate the plan briefly.
After coding, run migrations and tests, and report what was verified vs. not verified.
