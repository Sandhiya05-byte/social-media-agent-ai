from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class HookGenerationAgent(BaseAgent):
    name = "Hook Generation Agent"

    def execute(self, niche: str, creator_style: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        voice = creator_style or {
            "tone": "confident, practical, encouraging",
            "traits": ["clear", "supportive", "story-led"],
        }

        prompt = f"Generate multiple hook alternatives for {niche} using the creator's style: {voice}."
        raw = self.model.generate(prompt, {"niche": niche, "creator_style": voice})
        payload = self._parse_model_response(raw)

        hooks = [
            "Most creators don't struggle with the idea. They struggle with the system that keeps them stuck.",
            "If your content feels inconsistent, you don't need more motivation. You need a repeatable framework.",
            "The fastest way to grow a creator brand is not louder content. It is clearer positioning and sharper story arcs.",
        ]

        model_hooks = payload.get("hook_alternatives")
        if isinstance(model_hooks, list) and model_hooks:
            hooks = model_hooks

        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": self._now(),
            "completed_at": self._now(),
            "hook_alternatives": hooks,
            "summary": payload.get("summary") or f"Multiple hook variations generated for {niche}.",
        }
