from knowledge.structured_data import extract_json_ld_people


def test_extract_json_ld_people_from_nested_employee_array(html_fixtures_dir):
    # TC-61
    html = (html_fixtures_dir / "json_ld_person.html").read_text(encoding="utf-8")

    people = extract_json_ld_people(html)

    by_name = {p.name: p for p in people}
    assert set(by_name) == {"Jane Smith", "John Doe"}
    assert by_name["Jane Smith"].role == "Chief Executive Officer"
    assert by_name["Jane Smith"].company == "Acme Corp"  # inferred from enclosing Organization
    assert by_name["John Doe"].company == "Acme Subsidiary"  # explicit worksFor wins


def test_extract_json_ld_people_returns_empty_for_no_json_ld():
    # TC-62
    assert extract_json_ld_people("<html><body>no ld+json here</body></html>") == []
    assert extract_json_ld_people("") == []


def test_extract_json_ld_people_handles_malformed_json_defensively():
    # TC-63
    html = '<script type="application/ld+json">{not valid json</script>'
    assert extract_json_ld_people(html) == []


def test_extract_json_ld_people_drops_items_missing_name_or_role():
    # TC-64
    html = '<script type="application/ld+json">{"@type":"Person","name":"No Role"}</script>'
    assert extract_json_ld_people(html) == []


def test_extract_json_ld_people_on_real_theorg_page(html_fixtures_dir):
    # TC-65
    # theorg.com/Perplexity's real leadership content is entirely missing
    # from clean_text (trafilatura strips the <script> block, and the visible
    # card components don't render in the static fetch) but is present as
    # schema.org Person entries nested under the page's Organization JSON-LD
    # -- this is the motivating case for extract_json_ld_people (ADR-010).
    html = (html_fixtures_dir / "theorg_perplexity.html").read_text(encoding="utf-8")

    people = extract_json_ld_people(html)

    by_name = {p.name: p for p in people}
    assert "Aravind Srinivas" in by_name
    assert by_name["Aravind Srinivas"].role == "Cofounder, President, CEO"
    assert by_name["Aravind Srinivas"].company == "Perplexity"
    assert "Denis Yarats" in by_name
    assert "Johnny Ho" in by_name
    assert len(people) >= 15
