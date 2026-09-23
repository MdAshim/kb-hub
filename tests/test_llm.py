from types import SimpleNamespace

import pytest
import requests

from search.llm import GroqClient, LLMError, OllamaClient, get_llm


def test_get_llm_defaults_to_ollama(settings):
    # TC-69
    settings.LLM_PROVIDER = "ollama"
    assert isinstance(get_llm(), OllamaClient)


def test_get_llm_returns_groq_when_configured(settings, monkeypatch):
    # TC-70
    settings.LLM_PROVIDER = "groq"
    settings.GROQ_API_KEY = "test-key"
    monkeypatch.setattr("groq.Groq", lambda api_key: SimpleNamespace())
    assert isinstance(get_llm(), GroqClient)


def _fake_response(status_code=200, json_body=None, text=""):
    response = SimpleNamespace(status_code=status_code, text=text)
    response.json = lambda: json_body

    def _raise_for_status():
        if status_code >= 400:
            raise requests.HTTPError(f"{status_code} error", response=response)

    response.raise_for_status = _raise_for_status
    return response


def test_ollama_client_strips_json_fences_and_parses(monkeypatch, caplog):
    # TC-71
    client = OllamaClient()
    fenced = '```json\n{"answer": "hi"}\n```'
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: _fake_response(200, {"message": {"content": fenced}}),
    )

    with caplog.at_level("INFO"):
        result = client.complete_json(system="sys", user="What is the answer?")

    assert result == {"answer": "hi"}
    assert any("complete_json" in r.message for r in caplog.records)


def test_ollama_client_connection_error_raises_llm_error_and_logs(monkeypatch, caplog):
    # TC-72
    client = OllamaClient()

    def _raise(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("requests.post", _raise)

    with caplog.at_level("ERROR"), pytest.raises(LLMError, match="ollama serve"):
        client.complete_json(system="sys", user="hello")

    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_ollama_client_unparseable_json_raises_llm_error(monkeypatch):
    # TC-73
    client = OllamaClient()
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: _fake_response(200, {"message": {"content": "not json at all"}}),
    )

    with pytest.raises(LLMError):
        client.complete_json(system="sys", user="hello")
