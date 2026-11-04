"""Ollama-backed ModelInterface implementation with template fallback.

Only P0 scope: provides `OllamaModel`, which attempts local Ollama inference
and degrades to the existing `TemplateFallbackModel` behaviour whenever
Ollama is unavailable, misconfigured, or returns anything other than a
valid JSON payload.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.agents.base import ModelInterface, TemplateFallbackModel
from app.config import OLLAMA_BASE_URL, OLLAMA_ENABLED, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class OllamaModel(ModelInterface):
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        fallback: TemplateFallbackModel | None = None,
    ):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model or OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else OLLAMA_TIMEOUT_SECONDS
        self.fallback = fallback or TemplateFallbackModel()

    def generate(self, prompt: str, context: dict[str, Any]) -> str:
        raw = self._generate_via_ollama(prompt, context)
        if self._is_valid_json_response(raw):
            return raw
        logger.warning("Ollama response rejected; using template fallback.")
        return self.fallback.generate(prompt, context)

    def _generate_via_ollama(self, prompt: str, context: dict[str, Any]) -> str | None:
        payload = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "context": context,
            "stream": False,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                envelope = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
            logger.warning("Ollama request failed: %s", exc)
            return None

        model_output = envelope.get("response")
        if not isinstance(model_output, str):
            return None
        return model_output

    @staticmethod
    def _is_valid_json_response(raw: str | None) -> bool:
        if not isinstance(raw, str) or not raw.strip():
            return False
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict)
