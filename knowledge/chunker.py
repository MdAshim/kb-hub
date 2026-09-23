"""Split clean page text into overlapping, title-prefixed chunks."""

from __future__ import annotations

import re

CHARS_PER_TOKEN = 4


def chunk_text(text: str, title: str, size: int, overlap: int) -> list[str]:
    """Split on paragraphs, then pack into ~size tokens (approx 4 chars/token)
    with overlap. Prefix every chunk with "[{title}] "."""
    if not text or not text.strip():
        return []

    max_chars = max(size, 1) * CHARS_PER_TOKEN
    overlap_chars = max(overlap, 0) * CHARS_PER_TOKEN

    paragraphs = [p.strip() for p in re.split(r"\n+", text.replace("\r\n", "\n")) if p.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
        else:
            units.extend(_split_long_unit(paragraph, max_chars))

    chunks = _pack(units, max_chars, overlap_chars)
    return [f"[{title}] {chunk}" for chunk in chunks]


def _split_long_unit(text: str, max_chars: int) -> list[str]:
    """Break a single paragraph that's itself over max_chars into
    word-boundary pieces. Needed for the BeautifulSoup-fallback extraction
    path, whose get_text(" ", strip=True) output has no paragraph breaks at
    all -- without this, that text would form one giant unsplit "paragraph"."""
    words = text.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _pack(units: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= max_chars or not current:
            current = candidate
            continue

        chunks.append(current)
        tail = current[-overlap_chars:] if overlap_chars else ""
        seeded = f"{tail}\n\n{unit}" if tail else unit
        # If unit is itself large enough that even the overlap tail can't
        # share space with it, drop the overlap for this transition rather
        # than exceed max_chars (unit alone is always <= max_chars: it's
        # either an original short-enough paragraph or a pre-split piece).
        current = seeded if len(seeded) <= max_chars else unit
    if current:
        chunks.append(current)
    return chunks
