# Backlog: Epics, User Stories, Acceptance Criteria

Story IDs (US-xx) are referenced by `PLAN.md` tasks and `TESTING.md` cases.
Priority: **M** = must (in the brief), **S** = should (quality), **C** = could (nice to have).

## E1: CSV upload and URL harvesting

### US-01 Upload a URL file (M)
As a user, I can upload a CSV or XLSX file of URLs so that they are harvested.
- **Given** a valid `.csv` or `.xlsx` file, **when** I submit it, **then** a HarvestJob is created and I am redirected to its status page.
- **Given** a file with another extension, **when** I submit it, **then** I see a clear validation error and no job is created.
- **Given** a file larger than 5 MB, **when** I submit it, **then** it is rejected with an error.

### US-02 Parse and validate URLs (M)
As a user, I want only valid, unique URLs to be processed.
- The URL column is detected case-insensitively (`URL`, `url`, `Link`); if none is found, the first column containing http(s) values is used.
- Rows with empty or malformed URLs are skipped and counted in the job summary.
- Duplicate URLs within one file create one UrlRecord.
- An `ID` column, if present, is stored as `source_id`.

### US-03 Harvest content in the background (M)
As a user, I want scraping to run in the background so the upload does not time out.
- Each URL is fetched by its own background task.
- The upload request returns in under 2 seconds regardless of URL count.
- Each UrlRecord stores `status_code`, `raw_html`, `clean_text`, `title`, `fetched_at`.

### US-04 Fallback for protected or JS-rendered pages (S)
As a user, I want pages that block simple clients or need JavaScript to still be harvested.
- **Given** a 403/429 response, or extracted text under `MIN_TEXT_CHARS`, **when** fetching, **then** the page is retried with Playwright.
- `fetch_method` records `requests` or `playwright`.

### US-05 Store raw content in SQLite (M)
As a reviewer, I can inspect the raw scraped content.
- Raw HTML is stored unmodified in `UrlRecord.raw_html`.
- A failed fetch stores the error message and does not stop other URLs.

### US-06 See job progress (S)
As a user, I can see per-URL progress of a job.
- The job page lists each URL with status (pending / fetched / failed / indexed), HTTP code and method.
- The page refreshes automatically until the job is done.

## E2: Knowledge base pipeline

### US-07 Chunk and embed automatically (M)
As a user, I want harvested content added to the knowledge base without manual steps.
- When a URL is fetched successfully, an ingest task runs automatically.
- `clean_text` is split into chunks (~450 tokens, 50 overlap), each stored as a Chunk row.
- Each chunk is embedded and added to FAISS with `Chunk.id` as its vector id.

### US-08 Extract structured person records (S)
As a user, I want people identified as structured records, not only raw text.
- The LLM extracts `[{name, role, company, bio}]` from each page's text.
- Each person is saved as a Person row and a `kind="person"` chunk is created and embedded.
- Invalid LLM output is logged and the page still gets its text chunks.
- Where a page embeds schema.org `Person` data as JSON-LD, that's extracted too (no LLM call
  needed for those entries) and merged with the LLM's results, deduped by name (ADR-010).

### US-09 Persistent, rebuildable index (S)
As a developer, I want the index to survive restarts and be rebuildable.
- The FAISS index is saved to `FAISS_INDEX_PATH` after each ingest.
- `python manage.py rebuild_index` recreates the index from all Chunk rows.
- Re-harvesting a URL removes its old vectors before adding new ones.

## E3: Query and retrieval

### US-10 Natural-language search (M)
As a user, I can type a question and get relevant results.
- The query is embedded with the same model and searched in FAISS (top-k from settings).
- Person chunks receive a score boost.
- An empty query shows a validation message.

### US-11 Structured, friendly results (M)
As a user, I see results as person cards.
- Each card shows name, role, company, short summary and a link to the source URL.
- A short natural-language answer is shown above the cards.
- A collapsible section shows the retrieved chunks with similarity scores.
- The LLM is instructed to use only the retrieved context; results cite their source URL.

### US-12 Graceful degradation (S)
As a user, I still get results if the LLM is unavailable.
- On LLM timeout, error or invalid JSON, the raw top chunks are shown with a notice.
- If the index is empty, the page says no content has been indexed yet.

## E4: REST API

### US-13 List harvested URLs (M)
As an API client, I can call `GET /api/urls/`.
- Each item includes `url`, `status_code`, `raw_html` (plus `id`, `title`, `fetch_method`, `fetched_at`, `error`).
- Results are paginated (default page size 20).
- `?include_html=false` omits `raw_html`; `?status_code=` and `?job=` filter the list.

### US-14 Retrieve one URL (S)
- `GET /api/urls/{id}/` returns one record; unknown id returns 404.

### US-15 Search API (C)
- `POST /api/search/` with `{"query": "...", "top_k": 5}` returns the same structure the UI renders.

### US-16 Job status API (C)
- `GET /api/jobs/{id}/` returns job status and per-status counts.

## E5: Quality and delivery

### US-17 Documentation (M)
- README covers setup, run, usage, API and limitations; design docs are in `docs/`.

### US-18 Tests (S)
- Parser, chunker, vector store, retriever and API have automated tests that run without network access.

### US-19 Logging and errors (S)
- Fetch, ingest and LLM errors are logged with the URL or job id.
- The UI never shows a raw stack trace.

## E6: Submission requirements

Formal deliverables the client asked for on top of the working app. US-20 to US-22 are
marked bonus by the client; US-23 to US-25 are required submission artifacts, not features.

### US-20 Docker support (C, bonus)
As a reviewer, I want to run the app without setting up a Python environment by hand.
- A `Dockerfile` for the Django app.
- A `docker-compose.yml` running `web` and the huey worker as separate services, sharing
  the `data/` volume.
- Ollama runs on the host, not in Docker; `DEPLOYMENT.md` documents why (GPU access and
  model-download size/time are a poor fit for a container built for this assignment).
- `docker-compose up` brings up a working app against an already-running host Ollama.

### US-21 PEP 8 / lint compliance (C, bonus)
As a reviewer, I want the codebase to pass a standard linter cleanly.
- `ruff` (or `flake8` + `black`) added to `requirements.txt` as dev dependencies.
- The linter runs clean across the codebase (violations fixed, not suppressed).
- A documented command (e.g. `make lint`) runs it.

### US-22 Deployment documentation (C, bonus)
As a reviewer, I want to understand how this would be deployed for real.
- `docs/DEPLOYMENT.md` covers: running in Docker on a single VM, required env vars, and
  what must change for production (`DEBUG=False`, `ALLOWED_HOSTS`, a real secret key,
  serving static files).
- The doc states plainly that this is a documentation deliverable, not an actual cloud
  deployment carried out as part of the assignment.

### US-23 Model artifacts and regeneration instructions (S)
As a reviewer cloning the repo, I want to know why the FAISS index and database aren't
there and how to get a working one.
- README states plainly that `data/faiss.index` and `data/db.sqlite3` are not committed
  (gitignored, machine-specific).
- README documents regeneration: run migrations, then either upload the sample file, or
  run `python manage.py rebuild_index` if `Chunk` rows already exist in SQLite but the
  FAISS file is missing.
- README documents pulling the Ollama model as a required "artifact" step, since ingestion
  depends on it.

### US-24 Screenshots and demo video (S)
As a reviewer, I want to see the app working without necessarily running it myself.
- `docs/screenshots/` contains: upload page, job status page mid-run, job status done,
  search results with person cards, the raw-chunks fallback view, `/api/urls/` response,
  `/api/search/` response, Django admin showing a `Person` record.
- A demo script for a ~2 minute walkthrough video exists (drafted via the reusable prompt
  in `PROMPTS.md`); every screen it references actually exists and works.
- Recording the video itself is the client's responsibility, not part of this story.

### US-25 Submission notes document (S)
As a reviewer, I want the development process made transparent: what was unclear, how
long things took, and what the author would change.
- A top-level `SUBMISSION_NOTES.md` with three sections:
  - **Questions, assumptions and difficulties** — pulled from every phase's plan where an
    ambiguity, assumption, or real problem-and-fix came up (e.g. the circular-import fix,
    the 4xx/5xx fetcher bug, the two failed sample URLs, the `company_hint` source choice).
    1-3 sentences each: what was unclear/wrong, what was assumed or how it was fixed.
  - **Development time per task** — one row per phase (0 through 6) with start/end
    timestamps and elapsed time, computed from actual git log commit timestamps (that
    phase's commit vs. the previous one) — not estimated. Noted as AI-assisted development
    time, not manual coding time.
  - **Other Observations** (exact heading) — an honest take on what could be improved:
    what would be done differently with more time, any design compromise not fully settled,
    and anything about the assignment brief itself that was ambiguous or unclear.
