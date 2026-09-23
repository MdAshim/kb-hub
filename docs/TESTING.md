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
| TC-31 | US-04 | Mocked 4xx/5xx with no exception raised | Record marked `failed` per the LLD error table, even though the HTTP call itself succeeded |
| TC-32 | US-16 | GET /api/jobs/{id}/ unknown id | 404 |
| TC-33 | US-15 | POST /api/search/ missing `query` field | 400 |
| TC-34 | US-15 | POST /api/search/ `top_k` out of range | 400 |
| TC-35 | US-15 | POST /api/search/ LLM failure | `llm_ok` false, `people` empty, `sources` still populated |
| TC-36 | US-13 | `include_text=true` | `clean_text` present |
| TC-37 | US-13 | `job=` filter | Only matching rows |
| TC-38 | US-13 | `page_size=` param | Page size honored, `next` populated |
| TC-39 | US-14 | GET /api/urls/{id}/ with `include_html=false` | `raw_html`/`clean_text` still present (detail always includes both) |
| TC-40 | US-07 | `chunk_text()` on text with no paragraph breaks | Splits on word boundaries (BeautifulSoup-fallback case) |
| TC-41 | US-07 | `chunk_text()` on empty text | Returns `[]` |
| TC-42 | US-07 | Real `Embedder` (slow) | 384-dim, L2-normalized vectors |
| TC-43 | US-08 | Extractor: invalid items / duplicate names | Dropped / deduped |
| TC-44 | US-08 | Extractor on a contentless page (`informationevolution_404.html` fixture) | Returns no people |
| TC-45 | US-11 | Formatter: malformed top-level JSON shape | `llm_ok` false |
| TC-46 | US-11 | Formatter: malformed person items in an otherwise valid response | Skipped, not fatal |
| TC-47 | US-11 | Formatter `chunks` field | Always the full retrieved list, not just the LLM context slice |
| TC-48 | US-12 | Formatter: empty/whitespace-only `answer` | Treated as invalid, `llm_ok` false |
| TC-49 | US-12 | Formatter: explicit not-found `answer` | Accepted as valid, `llm_ok` true |
| TC-50 | US-11 | Formatter: LLM includes a tangential person | Passed through unfiltered (no code-side relevance filtering) |
| TC-51 | US-01 | Upload form: valid `.csv` | Form validates |
| TC-52 | US-09 | `fetch_url`/`ingest_url`: stale `error` from a prior failure | Cleared to `""` on the next success |
| TC-53 | US-09 | `ingest_url`: embedding/FAISS raises | Record marked `failed`; no partial vectors saved (Chunk/Person rows left for `rebuild_index`) |
| TC-54 | US-02 | `parse_url_file()` on the real sample xlsx | 5 urls, 0 skipped |
| TC-55 | US-10 | `retrieve()`: FAISS id with no matching Chunk row | Dropped silently (orphan handling) |
| TC-56 | US-10 | `retrieve()`: no FAISS hits | Returns `[]` |
| TC-57 | US-10 | Search page: query under 3 characters | Validation message shown |
| TC-58 | US-10 | Search page: no query submitted yet | Blank results area, no error/empty-index message |
| TC-59 | US-11 | Search page: `HX-Request` header | Returns the results fragment only, not the full page |
| TC-60 | US-11 | Search page: successful search | Person card rendered with name/company |
| TC-61 | US-08 | JSON-LD: nested `Organization.employee` Person array | Extracted with company inferred from the enclosing Organization (ADR-010) |
| TC-62 | US-08 | JSON-LD: no `<script type="application/ld+json">` present | Returns `[]` |
| TC-63 | US-08 | JSON-LD: malformed JSON in the script tag | Returns `[]`, never raises |
| TC-64 | US-08 | JSON-LD: Person entries missing name/role | Dropped |
| TC-65 | US-08 | JSON-LD on the real `theorg_perplexity.html` fixture | 16 real Perplexity leaders extracted (the ADR-010 motivating case) |
| TC-66 | US-19 | Unhandled exception in an API view | 500 `{"detail": "Internal error."}`, real exception never leaked into the response |
| TC-67 | US-19 | Unknown HTML page (`DEBUG=False`) | Friendly 404 page, no traceback |
| TC-68 | US-19 | Server error (`DEBUG=False`) | Friendly 500 page, no traceback |
| TC-69 | US-08 | `get_llm()` default provider | Returns `OllamaClient` |
| TC-70 | US-08 | `get_llm()` with `LLM_PROVIDER=groq` | Returns `GroqClient` |
| TC-71 | US-08 | `OllamaClient.complete_json()`: fenced ` ```json ` response | Fences stripped, parsed; INFO logged (US-19) |
| TC-72 | US-19 | `OllamaClient.complete_json()`: connection refused | `LLMError` ("run \`ollama serve\`"); ERROR logged |
| TC-73 | US-08 | `OllamaClient.complete_json()`: unparseable content | `LLMError` |

`test_home_page_returns_200` (the Phase 0 smoke test) is intentionally not assigned a TC id: it's an
infrastructure sanity check, not a story-specific test case, per principle 4 above (every TC maps to
a US-xx). TC-61 to TC-65 are mapped to US-08 as the closest existing story; the JSON-LD extraction
path itself is a design addition documented in `DECISIONS.md` ADR-010, not a separate backlog story.

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
