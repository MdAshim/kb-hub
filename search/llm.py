"""The only module allowed to call an LLM SDK/API directly."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import requests
from django.conf import settings


class LLMError(Exception):
    """Raised on any LLM connection, HTTP or JSON-parsing failure."""


class LLMClient(ABC):
    @abstractmethod
    def complete_json(self, system: str, user: str, timeout: int | None = None) -> dict:
        """Send system+user messages, return the parsed JSON response.
        Raises LLMError on any connection/parse failure."""


def _parse_json(content: str) -> dict:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Could not parse JSON from LLM response: {exc}") from exc


class OllamaClient(LLMClient):
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    def complete_json(self, system: str, user: str, timeout: int | None = None) -> dict:
        timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.ConnectionError as exc:
            raise LLMError("Ollama not reachable; run `ollama serve`") from exc
        except requests.RequestException as exc:
            raise LLMError(str(exc)) from exc

        content = response.json()["message"]["content"]
        return _parse_json(content)


class GroqClient(LLMClient):
    def __init__(self) -> None:
        from groq import Groq

        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    def complete_json(self, system: str, user: str, timeout: int | None = None) -> dict:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        content = completion.choices[0].message.content
        return _parse_json(content)


def get_llm() -> LLMClient:
    if settings.LLM_PROVIDER == "groq":
        return GroqClient()
    return OllamaClient()
