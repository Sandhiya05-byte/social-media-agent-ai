from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class HookGenerationAgent(BaseAgent):
    name = "Hook Generation Agent"

    def execute(
        self,
        niche: str,
        creator_style: dict[str, Any] | None = None,
        target_audience: str | None = None,
        research_results: dict | None = None,
        competitor_findings: dict | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        self.status = "running"
        started_at = self._now()

        audience = (target_audience or "creators").strip()
        research_sources = (research_results or {}).get("source_references") or []

        # Topic-anchored hooks: each references the actual campaign topic or a
        # real retrieved source title — never a generic creator-growth script.
        topic_hook = f"{niche}: here is what actually works for {audience}, based on live research."
        source_titles = [s.get("title") for s in research_sources if s.get("title")][:3]
        evidence_hook = (
            f"New coverage on \"{source_titles[0]}\" changes how {audience} should think about {niche}."
            if source_titles
            else f"{audience} keep asking the same question about {niche} — here is the direct answer."
        )
        question_hook = f"What if mastering {niche} took less time than {audience} expect?"
        hooks = [topic_hook, evidence_hook, question_hook]

        prompt = f"Generate multiple hook alternatives for {niche} targeting {audience} using the creator's style: {creator_style}."
        raw = self.model.generate(prompt, {"niche": niche, "target_audience": audience})
        payload = self._parse_model_response(raw)

        model_hooks = payload.get("hook_alternatives")
        if isinstance(model_hooks, list) and model_hooks:
            hooks = [str(h).strip() for h in model_hooks if str(h).strip()][:6] or hooks

        # Recommendation: the topic-anchored hook leads because it is specific
        # to this campaign and grounded in the supplied audience.
        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": started_at,
            "completed_at": self._now(),
            "niche": niche,
            "target_audience": audience,
            "hook_alternatives": hooks,
            "recommended_hook": hooks[0] if hooks else None,
            "recommendation_reason": (
                "Topic-anchored hook: names the exact campaign topic and audience, "
                "making the promise concrete rather than generic."
                if hooks and hooks[0] == topic_hook
                else "First hook returned by the configured model."
            ),
            "research_sources_used": len(research_sources),
            "summary": f"{len(hooks)} hooks generated for '{niche}' targeting {audience}.",
        }
