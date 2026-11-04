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
from app.agents.hook_generation_agent import HookGenerationAgent
from app.agents.trend_research_agent import TrendResearchAgent
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
    payload = {"ranked_topic_suggestions": [{"title": "Model topic", "score": 99}]}
    agent = TrendResearchAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps(payload)):
        result = agent.execute(niche="creator growth")
    assert result["ranked_topic_suggestions"][0]["title"] == "Model topic"


def test_trend_agent_falls_back_on_invalid_payload():
    agent = TrendResearchAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps({"unrelated": 1})):
        result = agent.execute(niche="creator growth")
    assert result["ranked_topic_suggestions"][0]["score"] == 96  # existing deterministic fallback
    assert result["status"] == "completed"


def test_competitor_agent_uses_model_observations():
    payload = {"observations": [{"source_url": "https://x", "summary": "Model signal", "signal_strength": "High"}]}
    agent = CompetitorIntelligenceAgent(model=OllamaModel())
    with patch.object(OllamaModel, "generate", return_value=json.dumps(payload)):
        result = agent.execute(niche="creator growth")
    assert result["observations"][0]["summary"] == "Model signal"


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
    assert result["hook_alternatives"][0].startswith("Most creators")  # deterministic fallback
    assert result["status"] == "completed"


# --- Full pipeline with default wiring disabled (template fallback intact) ---


def test_default_agents_complete_without_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    for agent_cls in (TrendResearchAgent, CompetitorIntelligenceAgent, BrandVoiceAgent, HookGenerationAgent):
        result = agent_cls().execute(niche="test niche")
        assert result["status"] == "completed"
