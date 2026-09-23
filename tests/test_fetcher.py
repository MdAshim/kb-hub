from types import SimpleNamespace

from harvest import fetcher


class FakePage:
    def __init__(self, html: str, status: int):
        self._html = html
        self._status = status

    def goto(self, url, timeout=None):
        return SimpleNamespace(status=self._status)

    def content(self):
        return self._html


class FakeBrowser:
    def __init__(self, html: str, status: int):
        self._html = html
        self._status = status

    def new_page(self):
        return FakePage(self._html, self._status)

    def close(self):
        pass


class FakeChromium:
    def __init__(self, html: str, status: int):
        self._html = html
        self._status = status

    def launch(self, headless=True):
        return FakeBrowser(self._html, self._status)


class FakePlaywright:
    def __init__(self, html: str, status: int = 200):
        self.chromium = FakeChromium(html, status)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _fake_requests_get(status_code: int, text: str):
    def _get(url, headers=None, timeout=None):
        return SimpleNamespace(status_code=status_code, text=text)

    return _get


def test_fetch_success_via_requests(monkeypatch, html_fixtures_dir):
    # TC-08: a normal 200 response is parsed via requests, no fallback.
    html = (html_fixtures_dir / "ok_page.html").read_text()
    monkeypatch.setattr(fetcher.requests, "get", _fake_requests_get(200, html))

    result = fetcher.fetch("https://example.com/leadership")

    assert result.error == ""
    assert result.method == "requests"
    assert result.status_code == 200
    assert result.html == html
    assert "Jane Smith" in result.text
    assert result.title == "Example Leadership Page"


def test_fetch_falls_back_to_playwright_on_403(monkeypatch, html_fixtures_dir):
    # TC-09: a 403 from requests triggers the Playwright path.
    monkeypatch.setattr(fetcher.requests, "get", _fake_requests_get(403, "Forbidden"))
    rendered_html = (html_fixtures_dir / "ok_page.html").read_text()
    monkeypatch.setattr(
        fetcher, "sync_playwright", lambda: FakePlaywright(rendered_html, status=200)
    )

    result = fetcher.fetch("https://example.com/leadership")

    assert result.method == "playwright"
    assert result.status_code == 200
    assert "Jane Smith" in result.text


def test_fetch_marks_http_error_status_as_failed(monkeypatch, html_fixtures_dir):
    # TC-31
    # A non-2xx status is a failure even with plenty of extracted text and no
    # exception raised (LLD error table: 4xx/5xx -> failed), so no fallback
    # is triggered here (404 isn't in FALLBACK_STATUS_CODES, text is long).
    html = (html_fixtures_dir / "ok_page.html").read_text()
    monkeypatch.setattr(fetcher.requests, "get", _fake_requests_get(404, html))

    result = fetcher.fetch("https://example.com/missing")

    assert result.method == "requests"
    assert result.status_code == 404
    assert result.error == "HTTP 404"
    assert "Jane Smith" in result.text  # still inspectable despite the failure


def test_fetch_falls_back_on_short_text(monkeypatch, html_fixtures_dir):
    # TC-10: a 200 response whose extracted text is under MIN_TEXT_CHARS still
    # falls back to Playwright (e.g. a JS shell page).
    short_html = (html_fixtures_dir / "js_shell.html").read_text()
    monkeypatch.setattr(fetcher.requests, "get", _fake_requests_get(200, short_html))
    rendered_html = (html_fixtures_dir / "ok_page.html").read_text()
    monkeypatch.setattr(
        fetcher, "sync_playwright", lambda: FakePlaywright(rendered_html, status=200)
    )

    result = fetcher.fetch("https://example.com/leadership")

    assert result.method == "playwright"
    assert "Jane Smith" in result.text
