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


def test_format_results_treats_empty_answer_as_invalid(monkeypatch, fake_llm):
    # An empty "answer" is treated the same as a missing/invalid one -- don't
    # rely on the model always following the "never leave answer blank"
    # prompt instruction.
    llm = fake_llm(response={"answer": "", "people": []})
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)
    chunks = [_chunk()]

    result = format_results("Who is the CFO of Oracle?", chunks)

    assert result.llm_ok is False
    assert result.answer is None
    assert result.chunks == chunks


def test_format_results_treats_whitespace_only_answer_as_invalid(monkeypatch, fake_llm):
    llm = fake_llm(response={"answer": "   \n  ", "people": []})
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)

    result = format_results("Who is the CEO of Microsoft?", [_chunk()])

    assert result.llm_ok is False


def test_format_results_accepts_explicit_not_found_answer(monkeypatch, fake_llm):
    llm = fake_llm(
        response={
            "answer": "I don't have information about Oracle's CFO in the retrieved content.",
            "people": [],
        }
    )
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)

    result = format_results("Who is the CFO of Oracle?", [_chunk()])

    assert result.llm_ok is True
    assert result.answer == "I don't have information about Oracle's CFO in the retrieved content."
    assert result.people == []


def test_format_results_passes_through_llm_people_list_unfiltered(monkeypatch, fake_llm):
    # This is a prompt-quality concern ("only include directly relevant
    # people"), not something format_results should filter in code -- it
    # can't judge relevance better than the LLM already can with the full
    # query in view. Confirm it just passes through whatever the LLM returns,
    # even a person who (from a human's read) looks tangential to the query.
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
                },
                {
                    "name": "Someone Tangential",
                    "role": "Regional Sales Rep",
                    "company": "Acme",
                    "summary": "Not who was asked about.",
                    "source_url": "https://example.com/b",
                },
            ],
        }
    )
    monkeypatch.setattr("search.formatter.get_llm", lambda: llm)

    result = format_results("Who is the CEO?", [_chunk()])

    assert result.llm_ok is True
    assert [p.name for p in result.people] == ["Jane Smith", "Someone Tangential"]
