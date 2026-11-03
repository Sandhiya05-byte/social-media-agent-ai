from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent


class VideoProductionAgent(BaseAgent):
    name = "Video Production Agent"

    def _build_srt(self, subtitle_path: Path, captions: list[str]) -> None:
        lines = []
        for index, caption in enumerate(captions, start=1):
            lines.append(f"{index}\n00:00:{(index - 1) * 2:02}.000 --> 00:00:{(index) * 2:02}.000\n{caption}\n")
        subtitle_path.write_text("\n".join(lines), encoding="utf-8")

    def execute(self, title: str, script: str, platform: str = "Instagram", captions: list[str] | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        output_dir = Path(__file__).resolve().parent.parent / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"{platform.lower()}_{title.lower().replace(' ', '_')[:30]}"
        video_path = output_dir / f"{base_name}.mp4"
        thumbnail_path = output_dir / f"{base_name}_thumb.png"
        subtitle_path = output_dir / f"{base_name}.srt"

        sample_captions = captions or [
            "Hook the audience immediately.",
            "Explain the problem clearly.",
            "Present the framework.",
            "Finish with a clear next step.",
        ]
        self._build_srt(subtitle_path, sample_captions)

        color = "#8b5cf6" if platform == "Instagram" else "#22d3ee" if platform == "YouTube" else "#10b981"
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x111827:s=1280x720:d=6",
            "-vf",
            f"drawtext=text='{title}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=(h-text_h)/2,drawbox=x=40:y=580:w=1200:h=100:color={color}@0.75:t=fill",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video_path),
        ]

        subprocess.run(command, check=True, capture_output=True, text=True)

        text_command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x111827:s=1280x720:d=1",
            "-vf",
            f"drawtext=text='{title}':fontcolor=white:fontsize=52:x=(w-text_w)/2:y=(h-text_h)/2",
            "-frames:v",
            "1",
            str(thumbnail_path),
        ]
        subprocess.run(text_command, check=True, capture_output=True, text=True)

        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": self._now(),
            "completed_at": self._now(),
            "platform": platform,
            "video_path": str(video_path),
            "thumbnail_path": str(thumbnail_path),
            "subtitle_path": str(subtitle_path),
            "captions": sample_captions,
            "limits": "Uses template-based motion and caption overlays; no unauthorized face or voice cloning.",
        }
