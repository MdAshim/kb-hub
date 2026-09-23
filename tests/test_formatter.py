from search.formatter import format_results
from search.retriever import RetrievedChunk


def _chunk(chunk_id=1, text="Jane Smith is CEO.", kind="person", score=0.9, url="https://example.com/a"):
    return RetrievedChunk(chunk_id=chunk_id, text=text, kind=kind, score=score, url=url)


def test_format_results_with_valid_llm_json(monkeypatch, fake_llm):
    # TC-21: valid LLM JSON produces a people list with source_url.
    llm = fake_llm(
        response={
            "answer": "Jane Smith is the CEO.",
            "people": [
                {
                    "name": "Jane Smith",
                    "role": "CEO",
                    "company": "Acme",
                    "summary": "Leads Acme.",
                    "source_url": "https://example.com/a",
                }
            ],
        }
    )
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)
    chunks = [_chunk()]

    result = format_results("Who is the CEO?", chunks)

    assert result.llm_ok is True
    assert result.answer == "Jane Smith is the CEO."
    assert len(result.people) == 1
    assert result.people[0].name == "Jane Smith"
    assert result.people[0].source_url == "https://example.com/a"
    assert result.chunks == chunks


def test_format_results_when_llm_raises(monkeypatch, fake_llm):
    # TC-22: LLM failure -> llm_ok False, chunks still returned.
    llm = fake_llm(fail=True)
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)
    chunks = [_chunk()]

    result = format_results("Who is the CEO?", chunks)

    assert result.llm_ok is False
    assert result.answer is None
    assert result.people == []
    assert result.chunks == chunks


def test_format_results_rejects_malformed_top_level_shape(monkeypatch, fake_llm):
    llm = fake_llm(response={"answer": "ok", "people": "not-a-list"})
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)

    result = format_results("Who is the CEO?", [_chunk()])

    assert result.llm_ok is False


def test_format_results_skips_malformed_person_items(monkeypatch, fake_llm):
    llm = fake_llm(
        response={
            "answer": "ok",
            "people": [
                {
                    "name": "Jane Smith",
                    "role": "CEO",
                    "company": "Acme",
                    "summary": "s",
                    "source_url": "u",
                },
                {"role": "missing name"},
                "not-a-dict",
            ],
        }
    )
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)

    result = format_results("Who is the CEO?", [_chunk()])

    assert result.llm_ok is True
    assert len(result.people) == 1
    assert result.people[0].name == "Jane Smith"


def test_format_results_chunks_field_is_full_list_not_context_slice(monkeypatch, fake_llm, settings):
    settings.SEARCH_CONTEXT_CHUNKS = 2
    llm = fake_llm(response={"answer": "ok", "people": []})
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)
    chunks = [_chunk(chunk_id=i) for i in range(5)]

    result = format_results("q", chunks)

    assert len(result.chunks) == 5
