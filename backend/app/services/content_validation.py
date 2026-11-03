import re
from typing import Any

from app.schemas.content import ContentValidationRequest, ValidationResult

PLATFORM_REQUIREMENTS = {
    "Instagram": ["caption or post copy is required", "short-form media should be concise and audience-first"],
    "YouTube": ["script is required for video narration", "title should clearly define the topic"],
    "LinkedIn": ["professional, insight-led language is recommended", "title should explain the value or learning"],
}

RISK_PATTERNS = [
    "guaranteed",
    "guaranteed reach",
    "viral",
    "100%",
    "secret formula",
    "automatically go viral",
    "instant growth",
    "hack",
]


def validate_content_payload(payload: ContentValidationRequest | dict[str, Any]) -> ValidationResult:
    if isinstance(payload, dict):
        payload = ContentValidationRequest(**payload)

    errors: list[str] = []
    warnings: list[str] = []
    platform_checks: list[str] = []

    if not payload.title or not payload.title.strip():
        errors.append("Title is required before approval.")

    if not payload.content or not payload.content.strip():
        errors.append("Content body is required.")

    if not payload.media_path and payload.platform in {"Instagram", "YouTube"}:
        warnings.append("Media asset is missing. A review should confirm that the export file is attached before publishing.")

    if payload.platform == "YouTube" and (not payload.script or not payload.script.strip()):
        errors.append("YouTube content requires a script or narration draft.")

    if payload.platform == "LinkedIn" and len(payload.content.strip()) < 40:
        warnings.append("LinkedIn copy is short; consider adding more professional context or proof points.")

    if payload.platform == "Instagram" and not payload.captions:
        warnings.append("Instagram caption list is empty. Add captions or a short call-to-action before approval.")

    if payload.platform == "Instagram" and len(" ".join(payload.captions)) > 2200:
        errors.append("Instagram copy exceeds the practical safe caption length for review.")

    if payload.platform == "LinkedIn" and len(payload.content.strip()) > 2200:
        warnings.append("LinkedIn post may be too long for easy reader comprehension; consider trimming it for clarity.")

    if not payload.script and payload.platform == "YouTube":
        warnings.append("Narration script is missing; a human reviewer should confirm the intended story before export.")

    if payload.title and len(payload.title.strip()) < 5:
        warnings.append("Title is very short and may be unclear to viewers.")

    if payload.content:
        words = re.findall(r"\b\w+\b", payload.content)
        if len(words) < 18:
            warnings.append("Content is very brief and may need more explanation or supporting points.")

    if payload.content and re.search(r"\b[A-Z]{5,}\b", payload.content):
        warnings.append("Large uppercase text is present, which can look like shouting and may reduce trust.")

    if payload.content and re.search(r"https?://", payload.content):
        warnings.append("External links are present; verify the destination and ensure the source is correctly attributed.")

    if payload.content:
        lower = payload.content.lower()
        for pattern in RISK_PATTERNS:
            if pattern in lower:
                warnings.append("Potential policy or trust risk flagged: language suggests exaggerated claims or guaranteed outcomes.")
                break

    if payload.platform in PLATFORM_REQUIREMENTS:
        platform_checks.extend(PLATFORM_REQUIREMENTS[payload.platform])

    if not errors and payload.title and payload.content:
        status = "passed"
    else:
        status = "failed"

    requires_human_review = bool(errors or warnings)

    return ValidationResult(
        status=status,
        errors=errors,
        warnings=warnings,
        requires_human_review=requires_human_review,
        platform_checks=platform_checks,
    )
