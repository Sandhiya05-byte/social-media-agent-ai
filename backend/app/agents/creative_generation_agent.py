from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.agents.base import BaseAgent
from app.config import GENERATED_DIR


class CreativeGenerationAgent(BaseAgent):
    name = "AI Clone and Creative Agent"

    def _build_template(
        self,
        title: str,
        platform: str,
        accent: tuple[int, int, int],
    ) -> Path:
        width_map = {"Instagram": 1080, "YouTube": 1920, "LinkedIn": 1200}
        height_map = {"Instagram": 1920, "YouTube": 1080, "LinkedIn": 1200}
        width = width_map.get(platform, 1080)
        height = height_map.get(platform, 1920)

        image = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(image)

        gradient_dark = (15, 23, 42)
        gradient_light = tuple(
            max(0, min(255, channel + 40)) for channel in accent
        )

        for y in range(height):
            ratio = y / max(height - 1, 1)
            color = tuple(
                int(gradient_dark[i] * (1 - ratio) + gradient_light[i] * ratio)
                for i in range(3)
            )
            draw.line((0, y, width, y), fill=color)

        draw.rounded_rectangle(
            (60, 60, width - 60, height - 60),
            radius=42,
            outline=(255, 255, 255),
            width=3,
        )

        try:
            font = ImageFont.truetype("arial.ttf", 70)
            sub_font = ImageFont.truetype("arial.ttf", 36)
        except OSError:
            font = ImageFont.load_default()
            sub_font = ImageFont.load_default()

        draw.text((150, 160), platform.upper(), fill=(180, 200, 255), font=sub_font)
        draw.text((150, 260), title[:32], fill=(255, 255, 255), font=font)
        draw.text(
            (150, 430),
            "Creator-approved template",
            fill=(200, 220, 255),
            font=sub_font,
        )

        output_dir = GENERATED_DIR / "creative"
        output_dir.mkdir(parents=True, exist_ok=True)

        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.lower()).strip("_")[:30]
        output_path = output_dir / f"{platform.lower()}_{slug or 'creative'}.png"
        image.save(output_path)
        return output_path

    def _fallback_content(
        self,
        campaign_topic: str,
        target_audience: str,
        campaign_objective: str,
        hook: str,
        research_findings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        research_findings = research_findings or {}
        source_titles = [
            (s.get("title") or "")[:90]
            for s in (research_findings.get("source_references") or [])
            if s.get("title")
        ][:3]
        keywords = [k for k in (research_findings.get("keywords") or [])[:6]]

        opening = hook or f"Want to understand {campaign_topic.lower()}?"
        evidence_line = (
            " Recent public coverage backs this up: " + "; ".join(f"\"{t}\"" for t in source_titles) + "."
            if source_titles
            else ""
        )
        keyword_line = (
            f" Watch for: {', '.join(keywords)} — these are the terms audiences actually use."
            if keywords
            else ""
        )
        return {
            "title": f"{campaign_topic}: A Practical Guide",
            "content": (
                f"{opening}\n\n"
                f"If you are {target_audience}, start by keeping your approach simple. "
                f"Break {campaign_topic.lower()} into small actions you can repeat. "
                "Choose one clear idea, explain it with a practical example, and give "
                "your audience one useful next step. Consistency comes from a process "
                "you can maintain, not from trying to do everything at once.\n\n"
                f"Objective: {campaign_objective}"
            ),
            "script": (
                f"{opening}\n\n"
                f"Here is the problem: most people treat {campaign_topic.lower()} like "
                "a burst of motivation instead of a repeatable system. That is why "
                "progress stops the moment things get busy.\n\n"
                f"So here is the framework. First, choose one specific goal for the "
                f"week and write it down. Second, create one useful piece of content "
                "around that goal, even if it is imperfect. Third, publish it, then "
                "look at the response and refine your next attempt."
                f"{evidence_line}\n\n"
                f"For {target_audience}, the practical example matters most: pick the "
                "single most relevant scenario and walk through it step by step, "
                "naming the specific tools or decisions involved."
                f"{keyword_line}\n\n"
                "Repeat this loop for four weeks and you will see which ideas your "
                f"audience actually wants from {campaign_topic.lower()}.\n\n"
                "Start with one small action today, and document what happens."
            ),
            "captions": [
                opening,
                f"Why {campaign_topic} matters for {target_audience}.",
                "The framework, step by step.",
                "One real example applied.",
                "Save this guide and try one step today.",
            ],
            "hashtags": ["#" + campaign_topic.split()[0].title(), "#LearnWithMe", "#HowTo"],
        }

    def _generate_content(self, context: dict[str, Any]) -> tuple[dict[str, Any], str]:
        campaign_topic = str(context.get("campaign_topic") or "Creator growth")
        target_audience = str(context.get("target_audience") or "beginner creators")
        campaign_objective = str(
            context.get("campaign_objective") or "Create useful educational content."
        )
        hooks = context.get("hooks") or []
        hook = str(context.get("recommended_hook") or (hooks[0] if hooks else ""))

        fallback = self._fallback_content(
            campaign_topic,
            target_audience,
            campaign_objective,
            hook,
            research_findings=context.get("research_findings") or {},
        )

        # Compact, bounded context: serializing the full research report
        # (dozens of long excerpts) overloads the 3B model's context window
        # and produces truncated/invalid JSON. Summaries only.
        def _compact_sources(findings: dict[str, Any], limit: int = 4) -> list[str]:
            return [
                f"{(s.get('title') or '')[:100]}"
                for s in (findings.get("source_references") or [])[:limit]
                if s.get("title")
            ]

        research_summary = {
            "keywords": (context.get("research_findings") or {}).get("keywords", [])[:8],
            "trending_subtopics": (context.get("research_findings") or {}).get("trending_subtopics", [])[:5],
            "sources": _compact_sources(context.get("research_findings") or {}),
        }
        competitor_summary = {
            "observations": [
                (o.get("summary") or "")[:140]
                for o in ((context.get("competitor_findings") or {}).get("observations") or [])[:3]
            ],
        }
        voice = context.get("brand_voice") or {}
        voice_summary = {
            "tone": voice.get("voice_profile", {}).get("tone"),
            "audience": voice.get("voice_profile", {}).get("campaign_context", {}).get("target_audience"),
        }

        prompt = f"""
You are an experienced social media content strategist.
Create original, practical content for this campaign.

Campaign topic: {campaign_topic}
Target audience: {target_audience}
Campaign objective: {campaign_objective}
Content type: {context.get("content_type", "short-form")}
Platform: {context.get("platform", "Instagram")}
Brand voice: {json.dumps(voice_summary, ensure_ascii=False)}
Research insights: {json.dumps(research_summary, ensure_ascii=False)}
Competitor insights: {json.dumps(competitor_summary, ensure_ascii=False)}
Recommended hook: {hook}

Return ONLY valid JSON. Do not use Markdown fences.
Use exactly these keys:
{{
  "title": "A concise engaging title",
  "content": "A complete useful social media post",
  "script": "A natural short-form narration script",
  "captions": ["caption or scene 1", "caption or scene 2", "caption or scene 3", "call to action"],
  "hashtags": ["#ExampleOne", "#ExampleTwo"]
}}

Requirements:
- Make the content specific to the topic and audience.
- Use a clear hook, practical explanation and useful call to action.
- Avoid fake statistics, guaranteed results and exaggerated claims.
- Keep the language natural and easy to understand.
- Do not claim that the content is viral or guaranteed to grow an account.
"""

        try:
            raw = self.model.generate(prompt, context)
            if not isinstance(raw, str) or not raw.strip():
                return fallback, "template_fallback"

            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            try:
                generated = json.loads(cleaned)
            except json.JSONDecodeError:
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start < 0 or end <= start:
                    return fallback, "template_fallback"
                generated = json.loads(cleaned[start : end + 1])

            if not isinstance(generated, dict):
                return fallback, "template_fallback"

            title = generated.get("title")
            content = generated.get("content")
            script = generated.get("script")
            captions = generated.get("captions")
            hashtags = generated.get("hashtags", [])

            # A 3B model may omit optional keys; require only title and body
            # and synthesize the narration script from the post body rather
            # than discarding an otherwise valid model response.
            if not (isinstance(title, str) and title.strip()) or not (isinstance(content, str) and content.strip()):
                return fallback, "template_fallback"

            if not (isinstance(script, str) and script.strip()):
                script = content

            if isinstance(captions, str):
                captions = [line.strip() for line in captions.splitlines() if line.strip()]

            if not isinstance(captions, list):
                captions = []

            captions = [
                str(item).strip() for item in captions if str(item).strip()
            ]

            if not captions:
                captions = fallback["captions"]

            if not isinstance(hashtags, list):
                hashtags = []

            return {
                "title": title.strip()[:180],
                "content": content.strip()[:5000],
                "script": script.strip()[:6000],
                "captions": captions[:12],
                "hashtags": [str(tag).strip() for tag in hashtags if str(tag).strip()][:15],
            }, "ollama"

        except Exception:
            return fallback, "template_fallback"

    def execute(
        self,
        title: str | None = None,
        platform: str = "Instagram",
        content: str | None = None,
        creator_media_path: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        self.status = "running"
        started_at = self._now()

        generation_context = {
            "campaign_topic": kwargs.get("campaign_topic") or title or "Creator growth",
            "target_audience": kwargs.get("target_audience", "beginner creators"),
            "campaign_objective": kwargs.get("campaign_objective", ""),
            "content_type": kwargs.get("content_type", "short-form"),
            "platform": platform,
            "brand_voice": kwargs.get("brand_voice", {}),
            "research_findings": kwargs.get("research_findings", {}),
            "competitor_findings": kwargs.get("competitor_findings", {}),
            "hooks": kwargs.get("hooks", []),
        }

        generated, generation_source = self._generate_content(generation_context)

        # Preserve compatibility with direct creative-generation requests.
        if content and not kwargs.get("campaign_topic"):
            generated["content"] = content

        final_title = generated["title"]

        accent = (
            (124, 58, 237)
            if platform == "Instagram"
            else (34, 211, 238)
            if platform == "YouTube"
            else (16, 185, 129)
        )

        output_path = self._build_template(
            title=final_title,
            platform=platform,
            accent=accent,
        )

        self.status = "completed"

        return {
            "agent": self.name,
            "status": self.status,
            "started_at": started_at,
            "completed_at": self._now(),
            "platform": platform,
            "title": final_title,
            "content": generated["content"],
            "script": generated["script"],
            "captions": generated["captions"],
            "hashtags": generated["hashtags"],
            "generation_source": generation_source,
            "generated_file": str(output_path),
            "preview_url": f"/generated/creative/{output_path.name}",
            "source_media": creator_media_path,
            "summary": f"Creative content generated for {platform}.",
            "limits": (
                "AI-generated copy with a template-based visual asset. "
                "No unauthorized face or voice cloning."
            ),
        }
