from __future__ import annotations

import os
import wave
from pathlib import Path

import pytest

from app.agents.video_production_agent import (
    VideoProductionAgent,
    sanitize_filename,
)

LONG_SCRIPT = (
    "Most creators do not struggle with ideas. They struggle with the system that keeps them consistent. "
    "Here is a simple framework you can repeat every week. First, pick one clear goal for your content. "
    "Second, produce one useful piece around that goal. Third, review what your audience responds to and "
    "refine your next attempt. Consistency comes from a process you can maintain, not from chasing every trend. "
    "Start with one small action today and document what happens. Over a few weeks you will see which ideas "
    "actually connect with people. Then double down on the ones that do. That is the whole playbook."
)


def _wav_file(path: Path, seconds: float = 1.0, rate: int = 22050) -> None:
    import struct

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(seconds * rate))


def test_synthesize_narration_single_wav(tmp_path):
    """One call produces exactly one valid narration WAV — no per-segment files."""
    agent = VideoProductionAgent()
    wav_path, duration = agent._synthesize_narration(["Segment one text.", "Segment two text."], tmp_path)

    assert wav_path.exists()
    assert wav_path.name == "narration.wav"
    assert duration > 0.05

    # Exactly one narration file and no leftover temporary files.
    wavs = list(tmp_path.glob("*.wav*"))
    assert [p.name for p in wavs] == ["narration.wav"]

    with wave.open(str(wav_path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    assert frames > 0
    assert rate > 0
    assert abs((frames / rate) - duration) < 0.01


def test_synthesize_narration_empty_text_raises(tmp_path):
    agent = VideoProductionAgent()
    with pytest.raises(RuntimeError, match="No narration text"):
        agent._synthesize_narration(["   ", ""], tmp_path)


def test_synthesize_narration_timeout_is_terminated_not_hanging(tmp_path, monkeypatch):
    """A stuck TTS subprocess is killed and reported as a failure, never hangs."""
    agent = VideoProductionAgent()
    monkeypatch.setattr(agent, "TTS_SUBPROCESS_TIMEOUT_SECONDS", 2.0)

    # A child command that sleeps forever simulates the SAPI deadlock.
    import subprocess
    import sys

    real_popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return real_popen(
            [sys.executable, "-c", "import time; time.sleep(600)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    monkeypatch.setattr("app.agents.video_production_agent.subprocess.Popen", fake_popen)

    with pytest.raises(RuntimeError, match="timed out"):
        agent._synthesize_narration(["Narration that will time out."], tmp_path)

    assert list(tmp_path.glob("*.wav*")) == []


def test_synthesize_narration_child_failure_raises(tmp_path, monkeypatch):
    """A non-zero child exit is surfaced as an error, never silently treated as success."""
    agent = VideoProductionAgent()

    import subprocess
    import sys

    real_popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        return real_popen(
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    monkeypatch.setattr("app.agents.video_production_agent.subprocess.Popen", fake_popen)

    with pytest.raises(RuntimeError, match="Offline TTS synthesis failed"):
        agent._synthesize_narration(["Narration that will fail."], tmp_path)

    assert list(tmp_path.glob("*.wav*")) == []


def test_synthesize_narration_invalid_wav_raises(tmp_path, monkeypatch):
    """A zero-byte or empty child output is rejected instead of trusted."""
    agent = VideoProductionAgent()

    import subprocess
    import sys

    real_popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        # Extract the temp wav target from the command and write an empty file.
        wav_target = Path(command[3])
        wav_target.write_bytes(b"")
        return real_popen(
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    monkeypatch.setattr("app.agents.video_production_agent.subprocess.Popen", fake_popen)

    with pytest.raises(RuntimeError):
        agent._synthesize_narration(["Narration with invalid output."], tmp_path)

    assert list(tmp_path.glob("*.wav*")) == []


def test_estimate_scene_timings_sum_to_duration():
    agent = VideoProductionAgent()
    texts = ["A short one.", "A considerably longer caption with many more characters in it.", "Third."]
    timings = agent._estimate_scene_timings_from_duration(texts, 30.0, 0.7)

    assert len(timings) == 3
    # Timings are ordered and end at (or just before) the narration duration.
    assert timings[0][0] == 0.0
    assert abs(timings[-1][1] - 30.0) < 0.1
    # Longer captions get proportionally more time.
    span_short = timings[0][1] - timings[0][0]
    span_long = timings[1][1] - timings[1][0]
    assert span_long > span_short


def test_srt_uses_narration_timings(tmp_path):
    agent = VideoProductionAgent()
    subtitle_path = tmp_path / "out.srt"
    timings = [(0.0, 2.5), (3.0, 6.25)]
    agent._build_srt(subtitle_path, ["First caption.", "Second caption."], timings)

    content = subtitle_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,500" in content
    assert "00:00:03,000 --> 00:00:06,250" in content


def test_srt_falls_back_without_timings(tmp_path):
    agent = VideoProductionAgent()
    subtitle_path = tmp_path / "out.srt"
    agent._build_srt(subtitle_path, ["First.", "Second."], None)

    content = subtitle_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in content
    assert "00:00:02,000 --> 00:00:04,000" in content


def test_execute_reports_short_script_honestly(tmp_path, monkeypatch):
    """A short script is rendered at its natural duration and flagged, not padded."""
    agent = VideoProductionAgent()
    monkeypatch.setattr(agent, "MIN_WORDS_FOR_TARGET_DURATION", 100000)

    result = agent.execute(
        title="Short Script Check",
        script="One short sentence. Two short sentences.",
        platform="YouTube",
        captions=[],
    )

    assert result["status"] == "completed"
    assert result["script_sufficient"] is False
    assert "nothing was padded with filler" in result["limits"]
    assert result["duration_seconds"] > 0
    assert result["duration_seconds"] < 60


def test_execute_long_script_targets_reported_range(tmp_path):
    result = VideoProductionAgent().execute(
        title="Long Script Check",
        script=LONG_SCRIPT,
        platform="Instagram",
        captions=[],
    )

    assert result["status"] == "completed"
    assert result["duration_seconds"] > 0
    assert result["video_format"] in {"mp4", "gif"}
    assert result["video_url"] is not None
    assert Path(result["video_path"]).exists()


def test_sanitize_filename_preserved():
    assert sanitize_filename("My Video: Title?") == "My_Video_Title"
    assert sanitize_filename("") == "campaign"


def test_return_fields_backward_compatible(tmp_path):
    result = VideoProductionAgent().execute(
        title="Interface Check",
        script="A compact script for the interface test.",
        platform="Instagram",
        captions=["One", "Two"],
    )

    for key in (
        "agent",
        "status",
        "started_at",
        "completed_at",
        "platform",
        "video_path",
        "video_format",
        "render_engine",
        "render_error",
        "thumbnail_path",
        "subtitle_path",
        "captions",
        "limits",
    ):
        assert key in result, f"missing legacy field: {key}"
    for key in ("duration_seconds", "audio_enabled", "video_url", "thumbnail_url", "subtitle_url"):
        assert key in result, f"missing extension field: {key}"
