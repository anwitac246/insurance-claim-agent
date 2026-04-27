"""
agents/image_summarizer.py
==========================
SecureWheel Insurance AI — Image Summarization Utility
------------------------------------------------------
Uses Groq's vision-capable model to analyse accident scene
photographs uploaded by the claimant and produce a structured
damage summary.  The summary is stored on ExtractedPhotos and
consumed by the Policy Validation Agent to cross-check whether
the visible damage matches the incident description on the
Claim Form.

Model: meta-llama/llama-4-scout-17b-16e-instruct  (Groq vision)
Fallback: if vision model unavailable, returns a placeholder.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

from groq import Groq

log = logging.getLogger("image_summarizer")

GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Supported image extensions for direct base64 encoding
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ─────────────────────────────────────────────────────────────
# PYDANTIC OUTPUT
# ─────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field


class ImageDamageSummary(BaseModel):
    """Structured output of the vision model's photo analysis."""
    damage_description: str = ""
    damage_areas: list[str] = Field(default_factory=list)   # e.g. ["front bumper", "hood"]
    damage_severity: str = "UNKNOWN"                        # MINOR | MODERATE | SEVERE | TOTAL_LOSS
    incident_type_inferred: str = "UNKNOWN"                 # collision | fire | flood | theft | other
    damage_consistent_with_claim: bool | None = None        # None = cannot determine
    manipulation_indicators: list[str] = Field(default_factory=list)
    ai_manipulation_score: float = 0.0                      # 0=clean, 1=manipulated
    image_count_analysed: int = 0
    raw_observations: str = ""                              # free-text from model


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _encode_image(file_path: str) -> tuple[str, str]:
    """
    Return (base64_data, media_type) for a local image file.
    Raises ValueError for unsupported formats.
    """
    ext = Path(file_path).suffix.lower()
    media_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif",
    }
    if ext not in media_map:
        raise ValueError(f"Unsupported image extension: {ext}")

    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_map[ext]


def _build_image_content(image_files: list[Any]) -> list[dict]:
    """
    Convert a list of RawFile objects to Groq vision message content blocks.
    Skips files that cannot be encoded.
    """
    content = []
    for raw_file in image_files:
        try:
            b64, mime = _encode_image(raw_file.file_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{b64}",
                },
            })
            log.debug(f"[ImageSummarizer] Encoded {raw_file.filename} ({mime})")
        except Exception as exc:
            log.warning(f"[ImageSummarizer] Skipping {raw_file.filename}: {exc}")
    return content


# ─────────────────────────────────────────────────────────────
# MAIN SUMMARIZER
# ─────────────────────────────────────────────────────────────

def summarize_images(
    image_files: list[Any],
    claim_type: str,
    accident_cause: str | None,
    groq_client: Groq,
) -> ImageDamageSummary:
    """
    Analyse accident scene photographs and return a structured damage summary.

    Args:
        image_files: List of RawFile objects whose file_path points to images.
        claim_type:  e.g. "OWN_DAMAGE", "THEFT", "FIRE"
        accident_cause: From the Claim Form (e.g. "rear collision")
        groq_client: Initialised Groq client.

    Returns:
        ImageDamageSummary with structured damage analysis.
    """
    if not image_files:
        log.info("[ImageSummarizer] No image files provided — skipping")
        return ImageDamageSummary()

    image_content = _build_image_content(image_files)
    if not image_content:
        log.warning("[ImageSummarizer] No encodable images — returning empty summary")
        return ImageDamageSummary(image_count_analysed=0)

    system_prompt = """You are a forensic vehicle damage assessment AI for SecureWheel Insurance.
Analyse the provided accident scene photographs and return ONLY valid JSON.
No markdown, no preamble.

JSON schema:
{
  "damage_description": "concise 2-3 sentence description of visible damage",
  "damage_areas": ["list of specific damaged vehicle areas, e.g. front bumper"],
  "damage_severity": "MINOR | MODERATE | SEVERE | TOTAL_LOSS",
  "incident_type_inferred": "collision | fire | flood | theft | vandalism | other",
  "damage_consistent_with_claim": true,
  "manipulation_indicators": ["list any signs of image editing or staging"],
  "ai_manipulation_score": 0.0,
  "image_count_analysed": 0,
  "raw_observations": "detailed free-text observations for adjuster review"
}

ASSESSMENT RULES:
- damage_consistent_with_claim: compare visible damage to the stated claim type and cause.
- ai_manipulation_score: 0.0 = photographic, no edits; 1.0 = clearly manipulated.
  Flag if: shadows are inconsistent, damage edges look digitally applied,
  metadata watermarks are absent, or surroundings look copy-pasted.
- damage_severity: TOTAL_LOSS if >75% of visible vehicle body is destroyed.
- Be objective. Do not guess beyond what is visible."""

    user_text = (
        f"Claim type: {claim_type}\n"
        f"Stated accident cause: {accident_cause or 'not provided'}\n\n"
        f"Analyse the {len(image_content)} photograph(s) attached and return JSON."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *image_content,
            ],
        },
    ]

    import json

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        data["image_count_analysed"] = len(image_content)
        return ImageDamageSummary(**data)

    except Exception as exc:
        log.error(f"[ImageSummarizer] Vision model call failed: {exc}")
        return ImageDamageSummary(
            damage_description=f"Image analysis failed: {exc}",
            image_count_analysed=len(image_content),
        )


# ─────────────────────────────────────────────────────────────
# FILTER HELPERS
# ─────────────────────────────────────────────────────────────

def filter_image_files(raw_files: list[Any]) -> list[Any]:
    """Return only image-type RawFile objects from the uploaded list."""
    return [
        f for f in raw_files
        if Path(f.file_path).suffix.lower() in _IMAGE_EXTS
        or (f.doc_type_hint or "").upper() in {"PHOTO", "PHOTOS", "IMAGE", "IMAGES", "DOC-011"}
    ]