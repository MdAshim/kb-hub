"""Fetch a URL's content: requests first, Playwright fallback for protected/JS pages."""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
import trafilatura
from bs4 import BeautifulSoup
from django.conf import settings
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
FALLBACK_STATUS_CODES = {403, 429}
RETRY_BACKOFF_SECONDS = 0.5


@dataclass
class FetchResult:
    status_code: int | None = None
    html: str = ""
    text: str = ""
    title: str = ""
    method: str = ""
    error: str = ""


def fetch(url: str) -> FetchResult:
    """Fetch url via requests, falling back to Playwright on 403/429 or short
    extracted text. Never raises; failures are reported in FetchResult.error."""
    try:
        result = _fetch_requests(url)
        if result.error:
            return result
        if _needs_fallback(result):
            result = _fetch_playwright(url)
            if result.error:
                return result
        return _finalize(result)
    except Exception as exc:  # noqa: BLE001 -- defensive: a URL failure must never
        # crash the task. Not logged here: harvest.tasks.fetch_url logs this
        # FetchResult.error one level up; logging it here too would double-log.
        return FetchResult(error=str(exc))


def _finalize(result: FetchResult) -> FetchResult:
    """A 4xx/5xx status is a failure even though no exception was raised
    (LLD error table: "Network error, 4xx/5xx -> Record failed"). html/text
    are kept so a failed fetch is still inspectable in admin."""
    if result.status_code is not None and result.status_code >= 400:
        result.error = f"HTTP {result.status_code}"
    return result


def _fetch_requests(url: str) -> FetchResult:
    headers = {"User-Agent": USER_AGENT}
    last_error = ""
    attempts = 1 + max(settings.FETCH_MAX_RETRIES, 0)
    for attempt in range(attempts):
        try:
            response = requests.get(
                url, headers=headers, timeout=settings.FETCH_TIMEOUT_SECONDS
            )
            html = response.text
            text = _extract_text(html)
            return FetchResult(
                status_code=response.status_code,
                html=html,
                text=text,
                title=_extract_title(html),
                method="requests",
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < attempts - 1:
                time.sleep(RETRY_BACKOFF_SECONDS)
    return FetchResult(error=last_error or "request failed")


def _needs_fallback(result: FetchResult) -> bool:
    if not settings.PLAYWRIGHT_FALLBACK:
        return False
    if result.status_code in FALLBACK_STATUS_CODES:
        return True
    return len(result.text) < settings.MIN_TEXT_CHARS


def _fetch_playwright(url: str) -> FetchResult:
    """Launch a fresh Chromium instance for this single call, then close it.

    Playwright's sync API cannot run inside a thread that already has an
    asyncio event loop; a plain Huey thread-worker OS thread has none, so
    it's safe here. Launching per call (rather than sharing one long-lived
    Browser) avoids any cross-call/cross-thread shared-state concerns and
    stays safe even if HUEY_WORKERS is raised above 1; the extra ~1-2s
    startup cost is a non-issue since this path only runs on the rare
    blocked/JS-heavy page.
    """
    timeout_ms = settings.FETCH_TIMEOUT_SECONDS * 1000
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                response = page.goto(url, timeout=timeout_ms)
                html = page.content()
                status_code = response.status if response else None
                return FetchResult(
                    status_code=status_code,
                    html=html,
                    text=_extract_text(html),
                    title=_extract_title(html),
                    method="playwright",
                )
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 -- same reasoning as fetch()'s catch above
        return FetchResult(error=str(exc), method="playwright")


def _extract_text(html: str) -> str:
    text = trafilatura.extract(html, include_tables=True)
    if text:
        return text
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()[:512]
    return ""
