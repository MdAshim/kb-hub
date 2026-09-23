from knowledge.chunker import chunk_text

TITLE = "Acme Leadership"


def test_chunk_text_respects_size_and_overlap_with_title_prefix():
    # TC-13: chunk_text on long text -> sizes within limit; overlap present; title prefix.
    size, overlap = 50, 10
    max_chars = size * 4
    overlap_chars = overlap * 4

    paragraphs = [
        f"Paragraph {i} contains several words about the leadership team and its "
        "history over many years of steady growth."
        for i in range(20)
    ]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text, TITLE, size=size, overlap=overlap)

    assert len(chunks) > 1
    prefix = f"[{TITLE}] "
    for chunk in chunks:
        assert chunk.startswith(prefix)
        assert len(chunk[len(prefix):]) <= max_chars

    first_body = chunks[0][len(prefix):]
    second_body = chunks[1][len(prefix):]
    tail = first_body[-overlap_chars:]
    assert second_body.startswith(tail)


def test_chunk_text_splits_a_single_unbroken_paragraph():
    # TC-40
    # The BeautifulSoup-fallback extraction path (get_text(" ", strip=True))
    # produces text with no paragraph breaks at all -- one giant "paragraph"
    # that must still be split on word boundaries instead of forming one
    # oversized chunk.
    text = " ".join(f"word{i}" for i in range(500))

    chunks = chunk_text(text, TITLE, size=50, overlap=10)

    assert len(chunks) > 1
    prefix = f"[{TITLE}] "
    for chunk in chunks:
        assert len(chunk[len(prefix):]) <= 50 * 4


def test_chunk_text_empty_input_returns_no_chunks():
    # TC-41
    assert chunk_text("", TITLE, size=50, overlap=10) == []
    assert chunk_text("   ", TITLE, size=50, overlap=10) == []
