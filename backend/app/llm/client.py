"""LLM client with three interchangeable backends.

mock  -> returns deterministic, structured responses (no model required)
local -> Ollama at settings.ollama_base_url (e.g. qwen2.5-coder)
api   -> OpenAI- or Anthropic-compatible endpoint if a key is configured

The agents in this project are written so that *mock mode performs real work*
(file edits, git diffs, test runs) without ever needing this client. The client
exists so ``local``/``api`` modes can drive the same agent graph with a real LLM.
"""
from __future__ import annotations

import json

import httpx

from app.config import settings


class LLMUnavailable(RuntimeError):
    pass


def complete(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1500) -> str:
    if settings.mode == "mock":
        # Mock mode never routes generation through here; agents are deterministic.
        return json.dumps({"mock": True, "note": "deterministic agents in mock mode"})
    if settings.mode == "local":
        return _ollama(system, user, temperature, max_tokens)
    return _api(system, user, temperature, max_tokens)


def _ollama(system: str, user: str, temperature: float, max_tokens: int) -> str:
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        r = httpx.post(f"{settings.ollama_base_url}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"]
    except Exception as exc:  # pragma: no cover - requires running Ollama
        raise LLMUnavailable(f"Ollama call failed: {exc}") from exc


def _api(system: str, user: str, temperature: float, max_tokens: int) -> str:
    if settings.anthropic_api_key:
        return _anthropic(system, user, temperature, max_tokens)
    if settings.openai_api_key:
        return _openai(system, user, temperature, max_tokens)
    raise LLMUnavailable("api mode selected but no API key is configured")


def _openai(system: str, user: str, temperature: float, max_tokens: int) -> str:  # pragma: no cover
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={
            "model": settings.api_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _anthropic(system: str, user: str, temperature: float, max_tokens: int) -> str:  # pragma: no cover
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.api_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]
