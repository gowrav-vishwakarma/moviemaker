"""Qwen Image Edit prompt builder."""

from __future__ import annotations

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import image_contract
from moviemaker.plugins.tagging import ensure_bound


def build_qwen_prompt(request: GenerationRequest) -> str:
    bound = ensure_bound(request, image_contract(max_images=6), strict=False)
    body = bound.rewritten.strip() if bound.rewritten else request.prompt.strip()
    if not bound.images:
        return body
    jobs = [f"{item.label} ({item.asset.name})" for item in bound.images]
    return f"{body}\nUse {', '.join(jobs)} as input. Preserve unmentioned details."
