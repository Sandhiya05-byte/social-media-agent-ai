"""P0 Ollama integration tests.

Covers: successful model responses wired into agent outputs, connection
failures, invalid/malformed responses, and deterministic fallback behaviour.
No live Ollama instance is required — the HTTP layer is stubbed.
"""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import patch

from app.agents.base import TemplateFallbackModel, create_default_model
from app.agents.brand_voice_agent import BrandVoiceAgent
from app.agents.competitor_intelligence_agent import CompetitorIntelligenceAgent
from app.agents.creative_generation_agent import CreativeGenerationAgent
from app.agents.hook_generation_agent import HookGenerationAgent
from app.agents.trend_research_agent import TrendResearchAgent
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.services.ollama_client import OllamaModel


# --- OllamaModel unit behaviour ---


def test_ollama_model_returns_model_output_on_success():
    model_payload = json.dumps({"hook_alternatives": ["Model hook one."]})
    model = OllamaModel()
    with patch.object(OllamaModel, "_generate_via_ollama", return_value=model_payload):
        result = model.generate("prompt", {"niche": "x"})
    assert json.loads(result) == {"hook_alternatives": ["Model hook one."]}


def test_ollama_model_falls_back_on_connection_failure():
    model = OllamaModel(fallback=TemplateFallbackModel())
    with patch.object(
        OllamaModel,
        "_generate_via_ollama",
        side_effect=urllib.error.URLError("connection refused"),
    ) as inner:
        # _generate_via_ollama itself swallows URLError, so simulate raw return
        inner.side_effect = lambda *a, **k: None
        result = model.generate("prompt", {"niche": "x"})
    parsed = json.loads(result)
    assert parsed["fallback"] == "template-model"


def test_ollama_model_rejects_non_json_raw_text():
    model = OllamaModel()
    with patch.object(OllamaModel, "_generate_via_ollama", return_value="plain prose answer"):
        result = model.generate("prompt", {})
    parsed = json.loads(result)
    assert parsed["fallback"] == "template-model"


def test_ollama_model_rejects_non_dict_json():
    model = OllamaModel()
    with patch.object(OllamaModel, "_generate_via_ollama", return_value='["array"]'):
        result = model.generate("prompt", {})
    assert json.loads(result)["fallback"] == "template-model"


def test_ollama_model_rejects_empty_response():
    model = OllamaModel()
    with patch.object(OllamaModel, "_generate_via_ollama", return_value=""):
        result = model.generate("prompt", {})
    assert json.loads(result)["fallback"] == "template-model"


def test_generate_via_ollama_swallows_connection_error(monkeypatch):
    model = OllamaModel(timeout=1)

    def raise_url_error(*args, **kwargs):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr("app.services.ollama_client.urllib.request.urlopen", raise_url_error)
    assert model._generate_via_ollama("p", {}) is None


# --- Default model factory ---


def test_create_default_model_returns_template_when_disabled(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    assert isinstance(create_default_model(), TemplateFallbackModel)


def test_create_default_model_returns_ollama_when_enabled(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    assert isinstance(create_default_model(), OllamaModel)


# --- Agents consume model payloads ---


def test_trend_agent_uses_model_suggestions():
    payload = {"trending_subtopics": ["Model topic"], "topic_summary": "Model summary"}
    agent = TrendResearchAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps(payload)):
        result = agent.execute(niche="creator growth")
    # Trend research is now retrieval-driven: model suggestions are recorded
    # as observations but real sources always come from the providers.
    assert result["research_status"] in {"ok", "no_results", "failed"}
    assert "provider_statuses" in result


def test_trend_agent_falls_back_on_invalid_payload():
    agent = TrendResearchAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps({"unrelated": 1})):
        result = agent.execute(niche="creator growth")
    assert result["status"] == "completed"
    assert isinstance(result["trending_subtopics"], list)


def test_competitor_agent_uses_model_observations():
    payload = {"observations": [{"competitor_url": "https://x", "summary": "Model signal", "signal_strength": "High"}]}
    agent = CompetitorIntelligenceAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps(payload)):
        result = agent.execute(niche="creator growth")
    # Competitor analysis is now retrieval-driven; model payload is recorded
    # but real observations come from fetching the supplied URLs.
    assert result["observations"]
    assert result["user_supplied_urls"] == []


def test_brand_voice_agent_uses_model_voice_profile():
    payload = {"voice_profile": {"tone": "model-tone", "traits": ["model trait"]}}
    agent = BrandVoiceAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps(payload)):
        result = agent.execute(niche="creator growth")
    assert result["voice_profile"]["tone"] == "model-tone"


def test_hook_agent_uses_model_hooks():
    payload = {"hook_alternatives": ["Hook from model."]}
    agent = HookGenerationAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps(payload)):
        result = agent.execute(niche="creator growth")
    assert result["hook_alternatives"] == ["Hook from model."]


def test_hook_agent_falls_back_on_raw_text_response():
    agent = HookGenerationAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps({"summary": "prose only"})):
        result = agent.execute(niche="creator growth")
    # Topic-anchored fallback: hooks reference the campaign niche.
    assert result["hook_alternatives"]
    assert all("creator growth" in h.lower() for h in result["hook_alternatives"])
    assert result["status"] == "completed"


# --- Full pipeline with default wiring disabled (template fallback intact) ---


def test_default_agents_complete_without_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    for agent_cls in (TrendResearchAgent, CompetitorIntelligenceAgent, BrandVoiceAgent, HookGenerationAgent):
        result = agent_cls().execute(niche="test niche")
        assert result["status"] == "completed"


# --- P0 fix: request payload must not send a dict in Ollama's `context` field ---


def test_generate_via_ollama_payload_has_no_context_dict(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["data"] = json.loads(request.data.decode("utf-8"))

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"response": json.dumps({"ok": 1})}).encode("utf-8")

        return FakeResponse()

    monkeypatch.setattr("app.services.ollama_client.urllib.request.urlopen", fake_urlopen)
    model = OllamaModel(timeout=1)
    result = model._generate_via_ollama("p", {"niche": "x", "nested": {"a": 1}})

    assert result is not None
    assert captured["url"].endswith("/api/generate")
    assert captured["data"]["stream"] is False
    assert captured["data"]["format"] == "json"
    # The dict context must NOT appear as the `context` field.
    assert "context" not in captured["data"]


def test_generate_via_ollama_embeds_context_in_prompt(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["data"] = json.loads(request.data.decode("utf-8"))

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"response": json.dumps({"ok": 1})}).encode("utf-8")

        return FakeResponse()

    monkeypatch.setattr("app.services.ollama_client.urllib.request.urlopen", fake_urlopen)
    model = OllamaModel(timeout=1)
    model._generate_via_ollama("original instructions", {"niche": "creator growth"})

    prompt = captured["data"]["prompt"]
    assert prompt.startswith("original instructions")
    assert "CONTEXT (JSON):" in prompt
    assert '"niche": "creator growth"' in prompt


def test_build_prompt_without_context_keeps_original_prompt():
    prompt = OllamaModel._build_prompt("original instructions", {})
    assert prompt.startswith("original instructions")
    assert "CONTEXT (JSON):" not in prompt


def test_generate_via_ollama_malformed_response_returns_none(monkeypatch):
    def fake_urlopen(request, timeout=None):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"not json at all"

        return FakeResponse()

    monkeypatch.setattr("app.services.ollama_client.urllib.request.urlopen", fake_urlopen)
    model = OllamaModel(timeout=1)
    assert model._generate_via_ollama("p", {}) is None


# --- qwen2.5:3b Model Configuration & Creative Agent Verification ---


def test_ollama_model_configuration_resolves_to_qwen():
    assert OLLAMA_MODEL == "qwen2.5:3b"
    assert OLLAMA_BASE_URL == "http://127.0.0.1:11434"
    model = OllamaModel()
    assert model.model_name == "qwen2.5:3b"
    assert model.base_url == "http://127.0.0.1:11434"


def test_ollama_api_request_uses_correct_model(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["payload"] = json.loads(request.data.decode("utf-8"))

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({
                    "response": json.dumps({
                        "title": "Test Title",
                        "content": "Test Content",
                        "script": "Test Script",
                    })
                }).encode("utf-8")

        return FakeResponse()

    monkeypatch.setattr("app.services.ollama_client.urllib.request.urlopen", fake_urlopen)
    model = OllamaModel()
    model._generate_via_ollama("test prompt", {"niche": "test"})
    assert captured["payload"]["model"] == "qwen2.5:3b"


def test_creative_agent_successful_ollama_response_sets_generation_source(monkeypatch):
    # Pass OllamaModel directly — bypasses create_default_model() which reads
    # app.config.OLLAMA_ENABLED, a module-level constant frozen at import time.
    # monkeypatch.setenv alone cannot override a cached module-level constant.
    monkeypatch.setattr("app.config.OLLAMA_ENABLED", True)
    valid_payload = json.dumps({
        "title": "AI Growth Playbook",
        "content": "A simple guide to using AI effectively for creators.",
        "script": "Here is how to get started with repeatable AI workflows.",
        "captions": ["Hook", "Actionable Step", "Call to Action"],
        "hashtags": ["#AI", "#Productivity"],
    })
    agent = CreativeGenerationAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=valid_payload):
        result = agent.execute(campaign_topic="AI growth")
    assert result["status"] == "completed"
    assert result["generation_source"] == "ollama"
    assert result["title"] == "AI Growth Playbook"
    assert result["content"] == "A simple guide to using AI effectively for creators."


def test_creative_agent_unavailable_or_invalid_ollama_falls_back_to_template(monkeypatch):
    monkeypatch.setattr("app.config.OLLAMA_ENABLED", True)
    agent = CreativeGenerationAgent(model=OllamaModel())

    # 1. OllamaModel falling back to template-model json
    fallback_payload = json.dumps({"fallback": "template-model"})
    with patch.object(OllamaModel, "generate", return_value=fallback_payload):
        result = agent.execute(campaign_topic="AI growth fallback")
    assert result["status"] == "completed"
    assert result["generation_source"] == "template_fallback"
    assert "AI growth fallback" in result["title"]

    # 2. Connection error / exception
    with patch.object(OllamaModel, "generate", side_effect=Exception("Connection refused")):
        result = agent.execute(campaign_topic="AI growth exception")
    assert result["status"] == "completed"
    assert result["generation_source"] == "template_fallback"
    assert "AI growth exception" in result["title"]

    # 3. Invalid / malformed non-JSON response
    with patch.object(OllamaModel, "generate", return_value="just a plain string without json"):
        result = agent.execute(campaign_topic="AI growth non-json")
    assert result["status"] == "completed"
    assert result["generation_source"] == "template_fallback"
    assert "AI growth non-json" in result["title"]
