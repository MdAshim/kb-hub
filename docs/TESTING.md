# Testing Strategy

## 1. Principles
- Tests never hit the network or a real LLM. Use saved HTML in `tests/fixtures/html/` and a `FakeLLM`.
- The embedding model is real but small; tests that need it are marked `@pytest.mark.slow`.
  A `FakeEmbedder` (deterministic hash vectors) is used for fast unit tests.
- FAISS tests use a temporary index path (`tmp_path`).
- Each test case (TC-xx) maps to a story (US-xx) in `BACKLOG.md`.

## 2. Levels
| Level | Tool | Scope |
|---|---|---|
| Unit | pytest | parser, fetcher decision logic, chunker, vector store, extractor parsing, formatter parsing |
| Integration | pytest-django | tasks with DB, retriever with FAISS + DB, API views |
| End-to-end (manual) | browser | upload sample file, watch job, run sample queries |

## 3. Fixtures
- `tests/fixtures/files/`: `valid.csv`, `valid.xlsx` (copy of `samples/Leadership_URL.xlsx`),
  `no_url_column.csv`, `duplicates.csv`, `bad_rows.csv`, `notes.txt`
- `tests/fixtures/html/`: one saved page per sample site, plus `js_shell.html` (near-empty body)
- `FakeLLM`: returns canned JSON, or raises / returns invalid text when configured
- `FakeEmbedder`: fixed-dimension deterministic vectors

## 4. Test cases
| ID | Story | Case | Expected |
|---|---|---|---|
| TC-01 | US-01 | Upload valid xlsx | Job created, redirect to job page |
| TC-02 | US-01 | Upload `.txt` | Form error, no job |
| TC-03 | US-01 | Upload file > 5 MB | Form error |
| TC-04 | US-02 | Column named `Link` | URLs detected |
| TC-05 | US-02 | No URL column | InvalidFileError / form error |
| TC-06 | US-02 | Duplicates and blank rows | Deduped; skipped count correct |
| TC-07 | US-02 | `ID` column | Stored as `source_id` |
| TC-08 | US-03 | fetch with mocked 200 response | status_code, raw_html, clean_text saved |
| TC-09 | US-04 | Mocked 403 | Playwright path called; method = playwright |
| TC-10 | US-04 | 200 with `js_shell.html` | Fallback triggered by short text |
| TC-11 | US-05 | Network exception | Record failed with error; other records unaffected |
| TC-12 | US-06 | Job page partial | Shows per-URL status rows |
| TC-13 | US-07 | chunk_text on long text | Sizes within limit; overlap present; title prefix |
| TC-14 | US-07 | ingest_url | Chunks created; vector count = chunk count |
| TC-15 | US-08 | Extractor with valid FakeLLM JSON | Person rows + person chunks |
| TC-16 | US-08 | Extractor with invalid JSON | Logged; text chunks still indexed |
| TC-17 | US-09 | Re-ingest same record | Old vectors removed; no duplicates |
| TC-18 | US-09 | rebuild_index | Index count equals Chunk count |
| TC-19 | US-10 | retrieve relevant query | Expected chunk in top 3 |
| TC-20 | US-10 | Person boost | Person chunk ranks above equal-score text chunk |
| TC-21 | US-11 | Formatter valid LLM JSON | people list with source_url |
| TC-22 | US-12 | Formatter LLM raises | llm_ok false, chunks returned |
| TC-23 | US-12 | Search on empty index | "Nothing indexed yet" / 503 |
| TC-24 | US-13 | GET /api/urls/ | 200, paginated, has url/status_code/raw_html |
| TC-25 | US-13 | `include_html=false` | raw_html absent |
| TC-26 | US-13 | `status_code=200` filter | Only matching rows |
| TC-27 | US-14 | GET unknown id | 404 |
| TC-28 | US-15 | POST /api/search/ empty query | 400 |
| TC-29 | US-15 | POST /api/search/ valid | 200 with answer/people/sources |
| TC-30 | US-16 | GET /api/jobs/{id}/ | counts per status |

## 5. Manual end-to-end checklist
- [ ] Fresh clone, follow README exactly
- [ ] Upload `samples/Leadership_URL.xlsx`; all 5 URLs reach `indexed` or a clear `failed`
- [ ] Note which sites needed Playwright; record in README limitations
- [ ] Queries: "Who is the CEO of Tesla?", "Apple senior vice presidents", "Perplexity leadership", "executives with finance background"
- [ ] Stop Ollama (quit the app / stop `ollama serve`) and confirm fallback results show
- [ ] `curl /api/urls/` and `?include_html=false`

## 6. Running
```bash
pytest                 # fast suite
pytest -m slow         # includes real embedding model
pytest --cov=.         # optional coverage (add pytest-cov)
```
