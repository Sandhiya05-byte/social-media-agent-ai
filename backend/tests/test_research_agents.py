from app.agents.brand_voice_agent import BrandVoiceAgent
from app.agents.competitor_intelligence_agent import CompetitorIntelligenceAgent
from app.agents.hook_generation_agent import HookGenerationAgent
from app.agents.trend_research_agent import TrendResearchAgent
from app.services.research_workflow import ResearchWorkflow


def test_trend_research_agent_ranks_topics():
    agent = TrendResearchAgent()
    result = agent.execute(niche="creator growth", source_urls=["https://example.com/rss"])

    assert result["status"] == "completed"
    assert result["agent"] == "Trend Research Agent"
    assert isinstance(result["trending_subtopics"], list)
    assert "provider_statuses" in result
    assert "source_references" in result
    assert "observations" in result


def test_competitor_intelligence_agent_collects_observations():
    agent = CompetitorIntelligenceAgent()
    result = agent.execute(niche="creator growth", competitor_urls=["https://example.com/a", "https://example.com/b"])

    assert result["status"] == "completed"
    assert result["agent"] == "Competitor Intelligence Agent"
    assert result["observations"]
    assert result["observations"][0]["competitor_url"]


def test_brand_voice_agent_extracts_style_profile():
    agent = BrandVoiceAgent()
    result = agent.execute(
        niche="creator growth",
        creator_samples=[
            "I help creators build a clear system for growth without overthinking the process.",
            "The best content strategy is simple, consistent and grounded in proof.",
        ],
    )

    assert result["status"] == "completed"
    assert result["voice_profile"]["tone"]
    assert result["voice_profile"]["traits"]


def test_hook_generation_agent_produces_alternatives():
    agent = HookGenerationAgent()
    result = agent.execute(niche="creator growth", creator_style={"tone": "confident, actionable"})

    assert result["status"] == "completed"
    assert result["agent"] == "Hook Generation Agent"
    assert len(result["hook_alternatives"]) >= 3


def test_combined_research_workflow_executes_all_agents():
    workflow = ResearchWorkflow()
    result = workflow.run(
        niche="creator growth",
        competitor_urls=["https://example.com/competitor-one", "https://example.com/competitor-two"],
        creator_writing_samples=["I help creators build simple systems that create repeatable momentum."],
        rss_sources=["https://example.com/rss-one", "https://example.com/rss-two"],
    )

    assert result["status"] == "completed"
    assert len(result["agent_statuses"]) == 4
    # Retrieval-driven research: unreachable example feeds yield no topic
    # sources, so the honest result may be empty — but the structured report
    # and provider statuses are always present.
    assert "provider_statuses" in result
    assert "source_references" in result
    assert "competitor_observations" in result
    assert "hook_alternatives" in result
    assert "recommended_hook" in result
