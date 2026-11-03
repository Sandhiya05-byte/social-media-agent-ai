from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


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


class BaseAgent(ABC):
    name: str = "Base Agent"
    status: str = "idle"

    def __init__(self, model: ModelInterface | None = None):
        self.model = model or TemplateFallbackModel()

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
