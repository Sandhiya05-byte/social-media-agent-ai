from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.agents.base import BaseAgent


class CreativeGenerationAgent(BaseAgent):
    name = "AI Clone and Creative Agent"

    def _build_template(self, title: str, platform: str, accent: tuple[int, int, int]) -> Path:
        width_map = {"Instagram": 1080, "YouTube": 1920, "LinkedIn": 1200}
        height_map = {"Instagram": 1920, "YouTube": 1080, "LinkedIn": 1200}
        width = width_map.get(platform, 1080)
        height = height_map.get(platform, 1920)

        image = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(image)

        gradient_dark = (15, 23, 42)
        gradient_light = tuple(max(0, min(255, channel + 40)) for channel in accent)

        for y in range(height):
            ratio = y / max(height - 1, 1)
            r = int(gradient_dark[0] * (1 - ratio) + gradient_light[0] * ratio)
            g = int(gradient_dark[1] * (1 - ratio) + gradient_light[1] * ratio)
            b = int(gradient_dark[2] * (1 - ratio) + gradient_light[2] * ratio)
            draw.line((0, y, width, y), fill=(r, g, b))

        draw.rounded_rectangle((60, 60, width - 60, height - 60), radius=42, outline=(255, 255, 255, 70), width=3)
        draw.rounded_rectangle((120, 120, width - 120, height - 180), radius=28, fill=(15, 23, 42, 80))

        try:
            font = ImageFont.truetype("arial.ttf", 70)
            sub_font = ImageFont.truetype("arial.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
            sub_font = ImageFont.load_default()

        draw.text((150, 160), platform.upper(), fill=(180, 200, 255), font=sub_font)
        draw.text((150, 260), title[:32], fill=(255, 255, 255), font=font)
        draw.text((150, 430), "Creator-approved template", fill=(200, 220, 255), font=sub_font)

        output_dir = Path(__file__).resolve().parent.parent / "generated" / "creative"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{platform.lower()}_{title.lower().replace(' ', '_')[:30]}.png"
        image.save(output_path)
        return output_path

    def execute(self, title: str, platform: str = "Instagram", content: str | None = None, creator_media_path: str | None = None, **kwargs) -> dict[str, Any]:
        self.status = "running"
        accent = (124, 58, 237) if platform == "Instagram" else (34, 211, 238) if platform == "YouTube" else (16, 185, 129)
        output_path = self._build_template(title=title, platform=platform, accent=accent)
        self.status = "completed"
        return {
            "agent": self.name,
            "status": self.status,
            "started_at": self._now(),
            "completed_at": self._now(),
            "platform": platform,
            "generated_file": str(output_path),
            "preview_url": f"/generated/creative/{output_path.name}",
            "source_media": creator_media_path,
            "content": content,
            "limits": "Template-based generation only; no unauthorized face or voice cloning.",
        }
