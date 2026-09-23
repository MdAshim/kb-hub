# Knowledge Base Hub

Turn a CSV/XLSX file of URLs into a searchable knowledge base about the people on those pages.

Upload a file of URLs, and the app scrapes each page, stores the raw content in SQLite, embeds it
into a FAISS vector index, and lets you ask natural-language questions like
*"Who is the CFO of Oracle?"* or *"Which Apple executives work on hardware?"*. Results come back as
structured person cards (name, role, company, bio, source). A REST API exposes the harvested data.

## Features
- **Upload & harvest**: CSV or XLSX upload, background scraping with a Playwright fallback for
  JS-heavy or bot-protected pages, raw HTML and HTTP status stored in SQLite.
- **Knowledge base pipeline**: automatic chunking, LLM-based person extraction, embeddings with
  `bge-small-en-v1.5`, stored in a persistent FAISS index.
- **Semantic search UI**: natural-language queries, person-aware retrieval, LLM-formatted result
  cards, with the retrieved source chunks and scores visible.
- **REST API**: `GET /api/urls/` (URL, status code, raw HTML), plus detail, job and search endpoints.

## Tech stack
Django 5 · Django REST Framework · Huey (SQLite backend) · requests + trafilatura · Playwright ·
sentence-transformers · FAISS · local LLM via Ollama (Groq optional) · HTMX

## Prerequisites
- Python 3.11 (on Windows, if `python --version` shows a different version, use the
  full path to a 3.11 install, e.g. `C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe`,
  or `py -3.11` if the Python launcher is installed)
- [Ollama](https://ollama.com/download) with a local model:
  ```bash
  ollama pull llama3.2:3b        # 8 GB RAM; use llama3.1:8b on 16 GB+
  ```
  Full instructions: [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)

## Quick start
```bash
git clone <repo-url> kb_hub && cd kb_hub
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env                                     # defaults to local Ollama; set OLLAMA_MODEL if needed
python manage.py migrate
```

Run (Ollama must be running; it usually starts automatically, otherwise `ollama serve`):
```bash
python manage.py runserver      # http://127.0.0.1:8000
python manage.py run_huey       # background worker
```

## Usage
1. Open `http://127.0.0.1:8000/` and upload `samples/Leadership_URL.xlsx`.
2. Watch the job page; each URL shows its status, HTTP code and fetch method.
3. When ingestion finishes, open **Search** and ask a question.

Sample queries:
- Who is the CEO of Tesla?
- List Apple's senior vice presidents and what they lead.
- Who are the leaders at Perplexity?
- Which executives have a background in finance?

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/urls/` | Harvested URLs with status code and raw HTML (paginated) |
| GET | `/api/urls/{id}/` | One harvested URL |
| GET | `/api/jobs/{id}/` | Harvest job progress |
| POST | `/api/search/` | Semantic search, returns structured people |

```bash
curl http://127.0.0.1:8000/api/urls/
curl "http://127.0.0.1:8000/api/urls/?include_html=false"
```
Full details: [docs/API.md](docs/API.md).

## Project structure
```
config/      Django settings, URLs, Huey config
harvest/     upload, parsing, fetching (HarvestJob, UrlRecord)
knowledge/   chunking, person extraction, embeddings, FAISS store (Person, Chunk)
search/      retrieval, LLM client, result formatting, search UI
api/         DRF serializers and views
templates/   HTML templates
samples/     sample input file
docs/        design documents
tests/       pytest suite and HTML fixtures
```

## Documentation
| Doc | Contents |
|---|---|
| [HLD](docs/HLD.md) | Architecture, components, non-functional requirements |
| [LLD](docs/LLD.md) | Modules, classes, function signatures |
| [DATABASE](docs/DATABASE.md) | ER diagram, tables, SQLite-FAISS mapping |
| [API](docs/API.md) | Endpoints and JSON contracts |
| [WORKFLOWS](docs/WORKFLOWS.md) | Sequence and state diagrams |
| [BACKLOG](docs/BACKLOG.md) | Epics, user stories, acceptance criteria |
| [PLAN](docs/PLAN.md) | Build phases and task checklist |
| [TESTING](docs/TESTING.md) | Test strategy and cases |
| [DECISIONS](docs/DECISIONS.md) | Architecture decision records |
| [LOCAL_SETUP](docs/LOCAL_SETUP.md) | Installing Ollama and the local models |

## Known limitations
- Some sites block automated clients or render content with JavaScript; these use the Playwright
  fallback and may still fail. Failures are recorded per URL and do not stop the job.
- FAISS is a local file index, suited to a single-machine deployment.
- Person extraction quality depends on the LLM; small local models (3B) are faster but less
  accurate than 8B. Results always link to their source page.
- On CPU-only machines the first LLM call is slow while the model loads.
