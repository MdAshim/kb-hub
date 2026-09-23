# Submission Notes

## Questions, assumptions and difficulties

Pulled from what actually came up phase by phase — not a reconstructed or padded list.

- **Circular import between `harvest.tasks` and `knowledge.tasks`** (Phase 2): `fetch_url`
  needs to call `ingest_url` directly on success, and both need a shared "is this job
  done" check. Putting that check in either task module would create a two-way import
  cycle. Resolved by moving it to `harvest/models.py` as a plain function
  (`update_job_status`), so only `harvest.tasks → knowledge.tasks` is one-directional.
- **`fetch()` silently treating 4xx/5xx as success** (Phase 1): the first real run against
  the sample file showed Oracle's page (404) and Tesla's page (403, after the Playwright
  retry) both marked `fetched` instead of `failed`, because no Python exception was
  raised. `LLD.md`'s error table says 4xx/5xx should be `failed`; fixed by adding a
  status-code check after any fallback attempt, while still saving `raw_html` for
  inspection.
- **Two real sample URLs turned out to be genuinely broken**, diagnosed rather than
  worked around: `informationevolution.com/company/` 404s because the site restructured
  since the assignment was authored (real content now lives at `/about`) — a stale
  sample URL, not a scraper bug. `ir.tesla.com/corporate` is blocked by an Akamai
  edge/WAF rule (confirmed via the actual block-page body) — genuine CDN-level bot
  detection, out of scope to defeat for this project. Documented in README rather than
  chased with increasingly elaborate workarounds.
- **`company_hint` for LLM extraction has no specified source** in `LLD.md`. Assumed
  `UrlRecord.title`, falling back to the URL's domain when there's no title — documented
  back into `LLD.md` once approved.
- **Test isolation gaps found the hard way, twice**: Huey's real queue file
  (`data/huey.db`) and the real FAISS index (`data/faiss.index`) are both outside
  Django's own test-database isolation (which covers SQLite automatically via an
  in-memory test DB). Two separate bugs surfaced from this — Phase 2's tests could
  enqueue real background tasks into the dev queue, and Phase 3's empty-index tests were
  silently passing against whatever real data happened to be sitting in the index from
  manual verification. Both fixed with a `"pytest" in sys.modules` override in
  `settings.py` pointing each at a throwaway path.
- **A small local LLM (`llama3.2:3b`) returned a blank `"answer"`** on 3 of 5 real
  stress-test queries, and padded `"people"` with everyone in context rather than just
  who was asked about — a real quality gap surfaced by manual testing, not something the
  original test suite caught (it only checked shape, not content quality). Fixed with a
  stronger prompt plus code-side validation that doesn't rely on the model behaving.
- **`informationevolution.com`'s failure and Oracle's failure turned out to be different
  problems** despite both showing "no people extracted": Oracle's page has real names in
  plain HTML that `trafilatura` drops for that specific card-grid layout (a genuine
  extraction-precision gap, left as a documented limitation); Perplexity's page (via
  `theorg.com`) had zero usable prose but *did* embed full `schema.org Person` data as
  JSON-LD — which `extractor.py`'s LLM path can't see (it only gets `clean_text`, not
  `raw_html`). That became `knowledge/structured_data.py` / ADR-010, a second,
  LLM-free extraction path.
- **DRF's default `Http404`→`NotFound` conversion leaks Django's generic message**
  (`"No UrlRecord matches the given query."`) instead of `API.md`'s documented
  `"Not found."` — caught by TC-27, fixed by overriding `get_object()`.
- **A logging regression from Phase 5's own work**: adding a Django `LOGGING` config
  caused every Huey-emitted log line to print twice, because `run_huey`'s
  `ConsumerConfig.setup_logger()` attaches its own handler directly to the *root*
  logger (not a `"huey"`-named one) when called with no explicit logger — colliding with
  Django's own root handler. Fixed by adding a `"huey"` logger entry with
  `propagate=False`, verified live rather than just reasoned through.
- **The fresh-clone README test surfaced several real gaps**: `source .venv/bin/activate`
  fails outright on Windows (no `bin/` directory in a Windows venv — confirmed, not
  assumed); the default `python` on this machine is 3.12, not 3.11; and the app is
  genuinely memory-hungry running Playwright + Ollama + the embedding model together —
  something the original README didn't warn about at all.
- **This development machine hit real resource exhaustion repeatedly** — Windows
  "paging file too small" errors, a Huey worker that silently stopped processing under
  memory pressure, and Docker Desktop's WSL2 VM alone dropping free RAM from ~3.7 GB to
  0.64 GB after a single build+run cycle (recovered via `wsl --shutdown`). These are
  genuinely about this dev box at the time, not the application — but they shaped a lot
  of this session's pacing and are worth knowing about if reproducing the same steps.

## Development time per phase

Computed from actual `git log` commit timestamps (start = the previous phase's last
commit, end = this phase's last commit) — not estimated. **This reflects AI-assisted
development time within this session's active work, not manual coding time, and is
bounded by session activity rather than true continuous elapsed calendar time** — real
gaps exist between turns (waiting on user review/approval between phases, background
task polling, and in Phase 6's case, genuine machine troubleshooting time), and none of
that is separated out from the raw commit-to-commit deltas below.

| Phase | Start (commit) | End (commit) | Elapsed |
|---|---|---|---|
| 0 — Project setup | 13:46:45 (`c130c16`) | 14:06:37 (`b910cc2`) | 19m52s |
| 1 — Upload & harvest | 14:06:37 (`b910cc2`) | 14:30:23 (`aa10735`) | 23m46s |
| 2 — Knowledge pipeline | 14:30:23 (`aa10735`) | 14:54:12 (`b181d68`) | 23m49s |
| *(interleaved: E6 backlog/plan addition, not phase work)* | 14:54:12 | 14:59:28 (`e2446ed`) | 5m16s |
| 2 — addendum (JSON-LD, ADR-010) | 14:59:28 (`e2446ed`) | 15:11:31 (`616c198`) | 12m03s |
| 3 — Search | 15:11:31 (`616c198`) | 16:13:08 (`f8e2d87`) | 1h01m |
| 4 — REST API | 16:13:08 (`f8e2d87`) | 16:46:12 (`85c7022`) | 33m04s |
| 5 — Quality & delivery | 16:46:12 (`85c7022`) | 17:34:26 (`abe3450`) | 48m14s |
| 6 — Submission packaging | 17:34:26 (`abe3450`) | *(this commit)* | ~3h+ |

Phase 6's duration is a clear outlier and shouldn't be read as "packaging took 6x longer
than any feature phase" — a large share of it was non-coding time: a Docker image build,
diagnosing and recovering from the WSL2/Docker memory issue above, an unrelated Ollama
self-update that transiently took the LLM offline mid-screenshot-capture, and a pause to
get explicit direction on how to handle the memory situation before proceeding.

## Other Observations

- **The small local LLM is the app's real accuracy ceiling**, not the retrieval or
  extraction pipeline around it. `llama3.2:3b` extracted 24 real Apple executives
  correctly in one run and near-identically in another, but also returned blank answers,
  transient 500s, and once needed a second attempt entirely — swapping to `llama3.1:8b`
  or Groq would likely improve reliability more than any further prompt engineering on
  the 3B model. This wasn't done here since it wasn't asked for, but it's the highest-
  leverage change I'd make with more time.
- **Two design compromises I'm not fully happy with, left as documented limitations
  rather than fixed**: Oracle's page loses real names to `trafilatura`'s content
  extraction for its specific card-grid layout (a precision bug in a third-party library,
  not something worth forking for this scope), and FAISS's retrieval has no relevance
  floor — a query about something never scraped still returns the closest *available*
  vectors rather than nothing, relying entirely on the LLM to say "not found." Both are
  documented (README, and a code comment + `API.md` note respectively) rather than
  silently left as surprises.
- **This app is more resource-hungry at run time than a take-home assignment's "runs on
  a laptop" framing might suggest.** Playwright + Ollama + the embedding model running
  together genuinely need real free RAM, not just an "8 GB machine" — confirmed
  repeatedly this session, not assumed. The README's Prerequisites now says so plainly,
  but it's worth flagging as a real characteristic of the design (three separate
  memory-hungry subsystems all running locally), not just an artifact of this particular
  dev machine being busy with other things.
- **Ambiguity in the assignment brief worth calling out**: nothing in the original brief
  specified what "close enough" person extraction should look like (exact name matching?
  fuzzy? human review?), so accuracy was judged qualitatively throughout rather than
  against a fixed bar — reasonable for a take-home, but a real evaluator would want to
  state this explicitly up front.
- **The person-card "summary" field is currently always empty** (`PersonResult.summary`)
  — the LLM prompt asks for it, but nothing in this session's real query results ever
  populated it with more than `""`. Worth a closer look at whether the prompt needs to
  ask more directly for a one-line summary distinct from `bio`, or whether `summary` is
  redundant with the answer text the model already produces.
