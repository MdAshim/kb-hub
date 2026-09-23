"""Opportunistic extraction of schema.org Person entries from a page's
JSON-LD (<script type="application/ld+json">) blocks. Cheap and
deterministic where a site embeds it; most sites don't, so this is a
complement to extractor.extract_people(), not a replacement. See ADR-010."""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

from .extractor import PersonData

logger = logging.getLogger(__name__)


def extract_json_ld_people(html: str) -> list[PersonData]:
    """Parse every JSON-LD script block in html and pull out schema.org
    Person entries at any nesting depth: a single top-level Person, a list,
    an @graph, or Person entries nested under an Organization's `employee`
    (or any other key). Never raises -- malformed/missing JSON-LD, or HTML
    that doesn't parse, just contributes no people."""
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    except Exception:
        logger.exception("Failed to parse HTML while looking for JSON-LD")
        return []

    people: list[PersonData] = []
    seen: set[str] = set()
    for script in scripts:
        try:
            data = json.loads(script.get_text())
        except (TypeError, ValueError):
            continue

        for node in _find_person_nodes(data, org_context=""):
            name = str(node.get("name", "")).strip()
            role = str(node.get("jobTitle", "")).strip()
            if not name or not role:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            people.append(
                PersonData(
                    name=name,
                    role=role,
                    company=_company_of(node),
                    bio=str(node.get("description", "")).strip(),
                )
            )
    return people


def _company_of(node: dict) -> str:
    works_for = node.get("worksFor")
    if isinstance(works_for, dict):
        name = works_for.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    elif isinstance(works_for, str) and works_for.strip():
        return works_for.strip()
    return str(node.get("_org_context", "")).strip()


def _find_person_nodes(node, org_context: str) -> list[dict]:
    """Recurse through the whole JSON-LD tree (any dict/list shape) looking
    for @type: "Person" nodes, tracking the nearest enclosing Organization's
    name as fallback company context for Person entries with no worksFor."""
    found: list[dict] = []
    if isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]

        if "Person" in types:
            person = dict(node)
            person.setdefault("_org_context", org_context)
            found.append(person)

        next_context = org_context
        if "Organization" in types and isinstance(node.get("name"), str):
            next_context = node["name"]

        for value in node.values():
            found.extend(_find_person_nodes(value, next_context))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_person_nodes(item, org_context))
    return found
