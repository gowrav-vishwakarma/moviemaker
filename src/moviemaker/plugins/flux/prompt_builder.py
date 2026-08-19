"""Flux prompt builder."""

from __future__ import annotations

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import image_contract
from moviemaker.plugins.tagging import ensure_bound


def build_flux_prompt(request: GenerationRequest) -> str:
    bound = ensure_bound(request, image_contract(max_images=4), strict=False)
    body = bound.rewritten.strip() if bound.rewritten else request.prompt.strip()
    if request.scene and not body:
        body = request.scene.prompt or request.scene.plot_summary
    if bound.images:
        labels = ", ".join(f.label for f in bound.images if f.label)
        return f"{body}\nUse {labels} as visual references. Preserve identity."
    return body
