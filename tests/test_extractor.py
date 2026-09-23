import trafilatura

from knowledge.extractor import PersonData, extract_people


def test_extract_people_with_valid_llm_json(monkeypatch, fake_llm):
    # TC-15: a valid FakeLLM JSON response produces PersonData records.
    llm = fake_llm(
        response={
            "people": [
                {"name": "Jane Smith", "role": "CEO", "company": "Acme", "bio": "Leads the company."},
                {"name": "John Doe", "role": "CFO", "company": "Acme", "bio": "Runs finance."},
            ]
        }
    )
    monkeypatch.setattr("knowledge.extractor.get_llm", lambda: llm)

    people = extract_people("Jane Smith is CEO. John Doe is CFO.", company_hint="Acme")

    assert people == [
        PersonData(name="Jane Smith", role="CEO", company="Acme", bio="Leads the company."),
        PersonData(name="John Doe", role="CFO", company="Acme", bio="Runs finance."),
    ]


def test_extract_people_drops_invalid_items_and_dedupes(monkeypatch, fake_llm):
    # TC-43
    llm = fake_llm(
        response={
            "people": [
                {"name": "Jane Smith", "role": "CEO"},
                {"name": "", "role": "Missing name"},
                {"name": "No Role"},
                {"name": "jane smith", "role": "Duplicate, different case"},
            ]
        }
    )
    monkeypatch.setattr("knowledge.extractor.get_llm", lambda: llm)

    people = extract_people("some text", company_hint="Acme")

    assert len(people) == 1
    assert people[0].name == "Jane Smith"


def test_extract_people_with_invalid_json_is_logged_and_returns_empty(monkeypatch, fake_llm):
    # TC-16: the LLM call fails (invalid JSON, in search.llm this surfaces as
    # LLMError) -> extract_people logs it and returns [] rather than raising.
    # (ingest_url still indexes the page's text chunks in this case; see
    # test_knowledge_tasks.py for that half of TC-16.)
    llm = fake_llm(fail=True)
    monkeypatch.setattr("knowledge.extractor.get_llm", lambda: llm)

    people = extract_people("some text", company_hint="Acme")

    assert people == []


def test_extract_people_on_contentless_page_finds_nobody(monkeypatch, fake_llm, html_fixtures_dir):
    # TC-44
    # informationevolution.com/company/ 404s (the site restructured; its real
    # leadership content now lives at /about instead) -- this saved fixture is
    # that dead page, used here as a realistic "no people on this page" case.
    html = (html_fixtures_dir / "informationevolution_404.html").read_text(encoding="utf-8")
    text = trafilatura.extract(html) or ""
    llm = fake_llm(response={"people": []})
    monkeypatch.setattr("knowledge.extractor.get_llm", lambda: llm)

    people = extract_people(text, company_hint="Information Evolution")

    assert people == []
