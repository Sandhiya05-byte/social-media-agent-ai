from pathlib import Path

from app.agents.creative_generation_agent import CreativeGenerationAgent
from app.agents.video_production_agent import VideoProductionAgent


def test_creative_generation_agent_creates_template_image():
    agent = CreativeGenerationAgent()
    result = agent.execute(title="Creator Growth Playbook", platform="Instagram")

    assert result["status"] == "completed"
    assert result["platform"] == "Instagram"
    assert Path(result["generated_file"]).exists()


def test_video_production_agent_generates_render_and_captions():
    agent = VideoProductionAgent()
    result = agent.execute(
        title="Creator Growth Playbook",
        script="Use a simple framework and keep the process visible.",
        platform="YouTube",
        captions=["Hook", "What is the problem?", "Explain the fix", "Call to action"],
    )

    assert result["status"] == "completed"
    assert Path(result["video_path"]).exists()
    assert Path(result["thumbnail_path"]).exists()
    assert Path(result["subtitle_path"]).exists()
    assert len(result["captions"]) == 4
