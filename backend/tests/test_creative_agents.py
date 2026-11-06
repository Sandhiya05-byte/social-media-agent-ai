from pathlib import Path

from app.agents.creative_generation_agent import CreativeGenerationAgent
from app.agents.video_production_agent import VideoProductionAgent, sanitize_filename


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
    assert result["video_format"] in {"mp4", "gif"}
    assert result["render_engine"] in {"ffmpeg", "pillow"}


def test_sanitize_filename_removes_path_traversal():
    cleaned = sanitize_filename("../../evil title/with:separators")
    assert ".." not in cleaned
    assert "/" not in cleaned
    assert "\\" not in cleaned
    assert ":" not in cleaned
    assert cleaned


def test_video_production_agent_sanitizes_tab_prefixed_campaign_titles():
    agent = VideoProductionAgent()
    title = "\tCreator Growth Playbook"
    platform = "Instagram"
    expected_base = sanitize_filename(f"{platform.lower()}_{title.lower().replace(' ', '_')[:30]}")

    result = agent.execute(
        title=title,
        script="Use a simple framework and keep the process visible.",
        platform=platform,
        captions=["Hook", "What is the problem?", "Explain the fix", "Call to action"],
    )

    assert result["status"] == "completed"
    assert Path(result["video_path"]).name.startswith(expected_base)
    assert Path(result["thumbnail_path"]).name == f"{expected_base}_thumb.png"
    assert Path(result["subtitle_path"]).name == f"{expected_base}.srt"
