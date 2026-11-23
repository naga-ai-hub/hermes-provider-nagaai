"""Offline tests: a stub ``providers`` package stands in for Hermes."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parent.parent / "__init__.py"
REGISTERED: list = []


@dataclass
class StubProfile:
    name: str
    api_mode: str = "chat_completions"
    aliases: tuple = ()
    display_name: str = ""
    description: str = ""
    signup_url: str = ""
    env_vars: tuple = ()
    base_url: str = ""
    auth_type: str = "api_key"
    fallback_models: tuple = ()
    default_headers: dict = field(default_factory=dict)
    default_aux_model: str = ""

    def fetch_models(self, *, api_key=None, base_url=None, timeout=8.0):
        return ["generic"]


def load_plugin():
    providers = types.ModuleType("providers")
    providers.register_provider = REGISTERED.append
    base = types.ModuleType("providers.base")
    base.ProviderProfile = StubProfile
    sys.modules["providers"] = providers
    sys.modules["providers.base"] = base
    spec = importlib.util.spec_from_file_location("nagaai_plugin", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model(model_id, endpoints=("chat.completions", "responses"), params=("tools",), operation="chat"):
    return {
        "id": model_id,
        "operations": [
            {"operation": operation, "endpoints": list(endpoints), "parameters": {p: {} for p in params}}
        ],
    }


CATALOG = {
    "data": [
        model("anthropic/claude-sonnet-5.5"),
        model("vendor/no-tools", params=("temperature",)),
        model("vendor/chat-only", endpoints=("chat.completions",)),
        model("vendor/image", operation="image"),
        model("anthropic/claude-sonnet-5.5"),
    ]
}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class PluginTest(unittest.TestCase):
    def setUp(self):
        REGISTERED.clear()
        self.plugin = load_plugin()

    def test_registers_a_responses_profile(self):
        (profile,) = REGISTERED
        self.assertEqual(profile.name, "nagaai")
        self.assertEqual(profile.api_mode, "codex_responses")
        self.assertEqual(profile.base_url, "https://api.naga.ac/v1")
        self.assertEqual(profile.env_vars[:2], ("NAGA_API_KEY", "NAGAAI_API_KEY"))

    def test_keeps_tool_capable_responses_chat_models_once(self):
        self.assertEqual(self.plugin.tool_capable_ids(CATALOG), ["anthropic/claude-sonnet-5.5"])

    def test_tolerates_malformed_payloads(self):
        for payload in (None, {}, {"data": "x"}, [1, {"id": 2}, {"id": "a", "operations": "x"}]):
            self.assertEqual(self.plugin.tool_capable_ids(payload), [])

    def test_fetch_sends_no_key_and_caches(self):
        body = json.dumps(CATALOG).encode()
        with mock.patch("urllib.request.urlopen", return_value=Response(body)) as urlopen:
            first = REGISTERED[0].fetch_models(api_key="secret")
            second = REGISTERED[0].fetch_models(api_key="secret")
        self.assertEqual(first, ["anthropic/claude-sonnet-5.5"])
        self.assertEqual(second, first)
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(request.get_header("X-naga-supported-endpoint"), "responses")

    def test_failed_fetch_returns_none_for_the_fallback_list(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertIsNone(REGISTERED[0].fetch_models())

    def test_custom_base_url_uses_the_generic_fetch(self):
        with mock.patch("urllib.request.urlopen") as urlopen:
            ids = REGISTERED[0].fetch_models(base_url="https://proxy.example/v1")
        self.assertEqual(ids, ["generic"])
        urlopen.assert_not_called()

    def test_refresh_drops_the_cache(self):
        body = json.dumps(CATALOG).encode()
        with mock.patch("urllib.request.urlopen", side_effect=[Response(body), Response(body)]) as urlopen:
            REGISTERED[0].fetch_models()
            REGISTERED[0].invalidate_catalog_cache()
            REGISTERED[0].fetch_models()
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
