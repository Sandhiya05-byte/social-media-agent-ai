from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class BrandVoiceAgent(BaseAgent):
    name = "Brand Voice Agent"

    def execute(self, niche: str, creator_samples: list[str] | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        samples = creator_samples or [
            "I help founders turn audience attention into real confidence and repeatable growth.",
            "The goal is not perfection. It is clarity, consistency, and a system that compounds over time.",
        ]

        prompt = f"Extract the creator's tone and writing traits for {niche} using the supplied writing samples."
        raw = self.model.generate(prompt, {"niche": niche, "creator_samples": samples})
        payload = self._parse_model_response(raw)

        voice_profile = {
            "tone": "confident, practical, encouraging",
            "traits": ["clear and specific", "story-led", "supportive but direct", "teaches within a framework"],
            "sentence_style": "Short sentences, actionable advice, positive momentum", 
            "approved_markers": ["use direct language", "focus on transformation", "avoid hype language"],
        }

        model_voice_profile = payload.get("voice_profile")
        if isinstance(model_voice_profile, dict) and model_voice_profile:
            voice_profile = model_voice_profile

        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": self._now(),
            "completed_at": self._now(),
            "creator_samples": samples,
            "voice_profile": voice_profile,
            "summary": payload.get("summary") or f"Brand voice profile created for {niche}.",
        }
