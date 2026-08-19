"""Passthrough prompt builder: user text + camera phrasing."""

from __future__ import annotations

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import generic_contract
from moviemaker.plugins.tagging import ensure_bound


def build_generic_prompt(request: GenerationRequest) -> str:
    bound = ensure_bound(request, generic_contract(), strict=False)
    parts: list[str] = []
    body = bound.rewritten.strip() if bound.rewritten else ""
    if body:
        parts.append(body)
    elif request.scene:
        if request.scene.prompt.strip():
            parts.append(request.scene.prompt.strip())
        elif request.scene.plot_summary.strip():
            parts.append(request.scene.plot_summary.strip())
    elif request.prompt:
        parts.append(request.prompt.strip())
    if request.scene:
        camera = request.scene.camera_phrase()
        if camera and "camera" not in " ".join(parts).lower():
            parts.append(f"Camera: {camera}.")
    return "\n".join(parts)
