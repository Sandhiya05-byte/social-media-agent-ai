from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ModelInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str, context: dict[str, Any]) -> str:
        pass


class TemplateFallbackModel(ModelInterface):
    def generate(self, prompt: str, context: dict[str, Any]) -> str:
        summary = {
            "prompt": prompt,
            "context": context,
            "fallback": "template-model",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(summary)


def create_default_model() -> ModelInterface:
    """Return the Ollama model when enabled, else the template fallback.

    Never raises: an import or configuration problem degrades to the
    existing TemplateFallbackModel behaviour.
    """
    if os.getenv("OLLAMA_ENABLED", "true").lower() not in {"0", "false", "no"}:
        try:
            from app.services.ollama_client import OllamaModel

            return OllamaModel()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Ollama model unavailable, using template fallback: %s", exc)
    return TemplateFallbackModel()


class BaseAgent(ABC):
    name: str = "Base Agent"
    status: str = "idle"

    def __init__(self, model: ModelInterface | None = None):
        self.model = model or create_default_model()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _parse_model_response(self, raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"summary": raw}

    @abstractmethod
    def execute(self, **kwargs) -> dict[str, Any]:
        pass
