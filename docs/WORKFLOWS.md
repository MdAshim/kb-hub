# Workflows

## 1. Upload and harvest
```mermaid
sequenceDiagram
  actor U as User
  participant V as Upload view
  participant P as Parser
  participant DB as SQLite
  participant Q as Huey queue
  participant W as Worker (fetch_url)
  participant F as Fetcher
  participant S as Website

  U->>V: POST file (csv/xlsx)
  V->>P: parse_url_file(file)
  P-->>V: urls, skipped
  V->>DB: create HarvestJob + UrlRecords (pending)
  V->>Q: enqueue fetch_url(id) per URL
  V-->>U: redirect to job page
  loop each URL
    Q->>W: fetch_url(id)
    W->>F: fetch(url)
    F->>S: GET (requests)
    alt 403/429 or text too short
      F->>S: load page (Playwright)
    end
    F-->>W: FetchResult
    W->>DB: save status_code, raw_html, clean_text, method
    W->>Q: enqueue ingest_url(id) if success
  end
  U->>V: job page polls (HTMX)
  V-->>U: per-URL status rows
```

## 2. Ingest into the knowledge base
```mermaid
sequenceDiagram
  participant Q as Huey queue
  participant I as Worker (ingest_url)
  participant DB as SQLite
  participant J as JSON-LD parser
  participant C as Chunker
  participant X as Extractor
  participant L as LLM
  participant E as Embedder
  participant VS as FAISS

  Q->>I: ingest_url(id)
  I->>DB: load UrlRecord, old chunk ids
  I->>VS: remove(old ids)
  I->>DB: delete old Chunks/Persons
  I->>J: extract_json_ld_people(raw_html)
  J-->>I: PersonData list (schema.org Person, ADR-010; no LLM call)
  I->>C: chunk_text(clean_text)
  C-->>I: text chunks
  I->>X: extract_people(clean_text)
  X->>L: JSON extraction prompt
  L-->>X: {"people": [...]}
  X-->>I: PersonData list
  Note over I: merge JSON-LD + LLM people, deduped by<br/>lowercased name; JSON-LD wins on a collision
  I->>DB: save Persons, text + person Chunks
  I->>E: embed_documents(chunk texts)
  E-->>I: vectors
  I->>VS: add(chunk ids, vectors), save()
  I->>DB: status = indexed
```

## 3. Search
```mermaid
sequenceDiagram
  actor U as User
  participant V as Search view / API
  participant R as Retriever
  participant E as Embedder
  participant VS as FAISS
  participant DB as SQLite
  participant F as Formatter
  participant L as LLM

  U->>V: query
  V->>R: retrieve(query, k)
  R->>E: embed_query(query)
  R->>VS: search(vector, k)
  VS-->>R: (chunk_id, score) list
  R->>DB: load Chunks + url + person
  R-->>V: ranked chunks (person boosted)
  V->>F: format_results(query, chunks)
  F->>L: context + JSON schema prompt
  alt LLM ok
    L-->>F: {answer, people}
    F-->>V: SearchResult(llm_ok=true)
  else error / bad JSON
    F-->>V: SearchResult(llm_ok=false, chunks)
  end
  V-->>U: answer, person cards, sources
```

## 4. UrlRecord state
```mermaid
stateDiagram-v2
  [*] --> pending
  pending --> fetching: fetch_url starts
  fetching --> fetched: page saved
  fetching --> failed: network / HTTP error
  fetched --> indexed: ingest ok
  fetched --> failed: embed / index error
  indexed --> fetching: re-harvest
  failed --> fetching: retry
  indexed --> [*]
  failed --> [*]
```

## 5. HarvestJob state
```mermaid
stateDiagram-v2
  [*] --> pending
  pending --> running: first task starts
  running --> done: all records indexed or failed
  done --> [*]
```
