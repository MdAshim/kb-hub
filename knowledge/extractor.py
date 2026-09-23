"""LLM-based extraction of person records from a page's text."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from search.llm import LLMError, get_llm

logger = logging.getLogger(__name__)

MAX_CHARS_PER_CALL = 12_000

SYSTEM_PROMPT = (
    "Extract every person described on this page. Return JSON only: "
    '{"people":[{"name":"","role":"","company":"","bio":""}]}. '
    "Use only the text given. If none, return {\"people\":[]}."
)


@dataclass
class PersonData:
    name: str
    role: str
    company: str
    bio: str


def extract_people(text: str, company_hint: str) -> list[PersonData]:
    """Send up to ~12k chars per call (split long pages, merge by name).
    Validate each item has name and role; drop invalid ones; dedupe by
    lowercased name. Never raises: any LLM/parse failure is logged and that
    slice simply contributes no people."""
    if not text or not text.strip():
        return []

    llm = get_llm()
    seen: dict[str, PersonData] = {}
    for slice_text in _slice(text, MAX_CHARS_PER_CALL):
        user = f"Company: {company_hint}\n\n{slice_text}"
        try:
            data = llm.complete_json(system=SYSTEM_PROMPT, user=user)
        except LLMError:
            logger.exception("Person extraction failed for a text slice")
            continue

        for item in _valid_items(data):
            key = item.name.lower()
            if key not in seen:
                seen[key] = item

    return list(seen.values())


def _valid_items(data: dict) -> list[PersonData]:
    people = data.get("people") if isinstance(data, dict) else None
    if not isinstance(people, list):
        return []

    results = []
    for item in people:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        role = str(item.get("role", "")).strip()
        if not name or not role:
            continue
        company = str(item.get("company", "")).strip()
        bio = str(item.get("bio", "")).strip()
        results.append(PersonData(name=name, role=role, company=company, bio=bio))
    return results


def _slice(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    slices: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            slices.append(current)
            current = word
    if current:
        slices.append(current)
    return slices
