# Demo video script (~2 minutes)

`PROMPTS.md` doesn't exist in this repo, so this script is written directly here instead
of being generated from a reusable prompt file. Recording the video itself is on the
project owner, not part of this deliverable — every screen below has been captured live
this session (see `docs/screenshots/`) and is known to work.

**Prerequisites for recording**: `python manage.py runserver`, `python manage.py run_huey`
running, Ollama running with `llama3.2:3b` pulled, and a clean `data/` (or just re-upload
the sample file — re-ingesting is idempotent).

---

## 0:00–0:15 — What this is
> "This is Knowledge Base Hub — you give it a spreadsheet of URLs, it scrapes each page,
> pulls out the people mentioned (executives, their roles, bios), and lets you ask
> natural-language questions about them."

Show: the empty **Upload** page (`/upload/`).

## 0:15–0:35 — Upload and watch it work
Upload `samples/Leadership_URL.xlsx` (5 real company leadership pages — Apple, Oracle,
Tesla, informationevolution.com, and Perplexity via theorg.com).

> "It redirects straight to the job page and updates itself every couple of seconds —
> no manual refresh."

Show: the job status page mid-run, rows changing from `pending` → `fetching` →
`indexed`/`failed` live.

## 0:35–0:55 — A job finishes, including the honest failures
> "Not every page cooperates. Tesla's investor relations page blocks scrapers outright,
> and this site restructured since the sample was made, so that URL 404s now. Both are
> recorded as `failed` with the actual error — the other three URLs aren't affected."

Show: the completed job page — 3 `indexed`, 2 `failed`, each row showing its real HTTP
status and fetch method (`requests` vs the Playwright fallback).

## 0:55–1:30 — Ask it something
Go to **Search**, type: *"Who is the CEO of Perplexity?"*

> "It embeds the question, searches the vector index, and asks a local LLM — running
> entirely on this machine via Ollama, nothing leaves the laptop — to answer using only
> what was actually retrieved."

Show: the answer sentence, the person card (name, role, company, a link back to the
source page), and expand **Sources** to show the ranked chunks with similarity scores
underneath.

> "If the model's unavailable or returns something unusable, it falls back to just
> showing the raw matching passages instead of guessing — it never invents an answer."

(Optional, if time allows: briefly show the fallback notice — e.g. by asking about
someone genuinely absent from the data, like Microsoft's CEO — to demonstrate it says
so plainly instead of hallucinating.)

## 1:30–1:50 — The API
> "Everything's also available as a REST API — for a client that wants the raw data
> instead of the UI."

Show (terminal or browser): `curl http://127.0.0.1:8000/api/urls/` and
`curl -X POST http://127.0.0.1:8000/api/search/ -d '{"query": "Who is the CEO of Perplexity?"}'`
— same structured JSON the UI itself rendered.

## 1:50–2:00 — Wrap
> "SQLite holds everything durably; the vector index can always be rebuilt from it with
> one command if it's ever lost. That's the whole loop: upload, harvest, ask."
