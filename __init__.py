"""NagaAI model provider for Hermes Agent.

Registers ``nagaai`` over NagaAI's OpenAI Responses endpoint. The ``/model``
picker lists the chat models that accept tool calls on that endpoint, read
from NagaAI's public catalog (``GET /v1/models``, no key sent).
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from providers.base import ProviderProfile

from providers import register_provider

logger = logging.getLogger(__name__)

BASE_URL = "https://api.naga.ac/v1"
USER_AGENT = "hermes-provider-nagaai/1.0.1"
# Hermes speaks the Responses API in this mode; the catalog header narrows the
# list to models served on that endpoint.
ENDPOINT = "responses"

# Shown only when the live catalog is unreachable; each id accepts tools on
# the Responses endpoint.
FALLBACK_MODELS = (
    "anthropic/claude-sonnet-5.5",
    "anthropic/claude-opus-5.5",
    "openai/gpt-6.1-sol",
    "google/gemini-3.5-flash",
    "deepseek/deepseek-v4.1-flash",
    "minimax/minimax-m3",
)


def tool_capable_ids(payload: Any) -> list[str]:
    """Ids of chat models that accept ``tools`` on the Responses endpoint."""
    entries = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        return []
    ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        if any(_serves_tools(op) for op in entry.get("operations") or ()):
            if entry["id"] not in ids:
                ids.append(entry["id"])
    return ids


def _serves_tools(operation: Any) -> bool:
    if not isinstance(operation, dict) or operation.get("operation") != "chat":
        return False
    endpoints = operation.get("endpoints") or ()
    parameters = operation.get("parameters") or {}
    return ENDPOINT in endpoints and isinstance(parameters, dict) and "tools" in parameters


_CATALOG: dict[str, list[str]] = {}


class NagaAIProfile(ProviderProfile):
    """NagaAI with a picker limited to tool-capable models."""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        caller = (base_url or "").strip().rstrip("/")
        if caller and caller != BASE_URL:
            # A user-set base URL is someone else's catalog: use the generic fetch.
            return super().fetch_models(api_key=api_key, base_url=base_url, timeout=timeout)
        if "ids" not in _CATALOG:
            ids = self._fetch_catalog(timeout)
            if not ids:
                return None  # Hermes falls back to fallback_models
            _CATALOG["ids"] = ids
        return _CATALOG["ids"]

    def invalidate_catalog_cache(self) -> None:
        _CATALOG.clear()

    @staticmethod
    def _fetch_catalog(timeout: float) -> list[str]:
        request = urllib.request.Request(
            BASE_URL + "/models",
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
                "x-naga-supported-endpoint": ENDPOINT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return tool_capable_ids(json.loads(response.read().decode()))
        except Exception as exc:  # any failure falls back to fallback_models
            logger.debug("nagaai: catalog fetch failed: %s", exc)
            return []


nagaai = NagaAIProfile(
    name="nagaai",
    aliases=("naga",),
    api_mode="codex_responses",
    display_name="NagaAI",
    description="NagaAI — models from OpenAI, Anthropic, Google, DeepSeek and others over the Responses API",
    signup_url="https://naga.ac/dashboard/api-keys",
    # Hermes reads key variables in order: NAGA_API_KEY is the name every NagaAI
    # example uses; NAGAAI_API_KEY keeps 1.0.0 setups working.
    env_vars=("NAGA_API_KEY", "NAGAAI_API_KEY", "NAGAAI_BASE_URL"),
    base_url=BASE_URL,
    auth_type="api_key",
    fallback_models=FALLBACK_MODELS,
    default_aux_model="google/gemini-3.5-flash-lite",
)

register_provider(nagaai)
