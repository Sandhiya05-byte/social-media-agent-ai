from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AgentRegistration:
    name: str
    factory: Callable[[], Any]
    description: str = ""
    phase: str = "general"


class AgentRegistry:
    def __init__(self):
        self._registry: dict[str, AgentRegistration] = {}
        self._execution_order: list[str] = []

    def register(self, name: str, factory: Callable[[], Any], description: str = "", phase: str = "general") -> None:
        self._registry[name] = AgentRegistration(name=name, factory=factory, description=description, phase=phase)
        if name not in self._execution_order:
            self._execution_order.append(name)

    def register_default_agents(self) -> None:
        if self._registry:
            return

        from app.agents.brand_voice_agent import BrandVoiceAgent
        from app.agents.competitor_intelligence_agent import CompetitorIntelligenceAgent
        from app.agents.creative_generation_agent import CreativeGenerationAgent
        from app.agents.hook_generation_agent import HookGenerationAgent
        from app.agents.publishing_scheduling_agent import PublishingSchedulingAgent
        from app.agents.trend_research_agent import TrendResearchAgent
        from app.agents.video_production_agent import VideoProductionAgent

        registrations = [
            ("Trend Research Agent", TrendResearchAgent, "Finds ranked topic opportunities from public sources.", "research"),
            ("Competitor Intelligence Agent", CompetitorIntelligenceAgent, "Captures public competitor signals and content observations.", "research"),
            ("Brand Voice Agent", BrandVoiceAgent, "Learns the creator's tone, traits, and writing style.", "research"),
            ("Hook Generation Agent", HookGenerationAgent, "Creates multiple hook alternatives grounded in the creator's voice.", "research"),
            ("AI Clone and Creative Agent", CreativeGenerationAgent, "Creates branded templates and authorized creator-safe creative mockups.", "creative"),
            ("Video Production Agent", VideoProductionAgent, "Builds short-form video drafts with captions and thumbnails.", "creative"),
            ("Publishing and Scheduling Agent", PublishingSchedulingAgent, "Handles scheduling, human approval safeguards, and publishing preparation.", "publishing"),
        ]

        for name, factory, description, phase in registrations:
            self.register(name, factory, description, phase)

    def get(self, name: str):
        self.register_default_agents()
        registration = self._registry.get(name)
        if registration is None:
            raise KeyError(f"Agent '{name}' is not registered.")
        return registration.factory()

    def list_agents(self) -> list[dict[str, str]]:
        self.register_default_agents()
        ordered = []
        for name in self._execution_order:
            registration = self._registry[name]
            ordered.append({
                "name": registration.name,
                "description": registration.description,
                "phase": registration.phase,
            })
        return ordered

    def execution_order(self) -> list[str]:
        self.register_default_agents()
        return list(self._execution_order)
