"""Wan SPACE prompt builder."""

from __future__ import annotations

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import wan_contract
from moviemaker.plugins.tagging import ensure_bound


def build_wan_prompt(request: GenerationRequest) -> str:
    bound = ensure_bound(request, wan_contract(), strict=False)
    scene = request.scene
    body = (bound.rewritten or request.prompt or (scene.prompt if scene else "") or (scene.plot_summary if scene else "")).strip()
    if body.lower().startswith("subject:"):
        return body
    subject = scene.title if scene else "the subject"
    performance = body or "performs naturally for camera"
    extra = ""
    if request.project.mood:
        extra = f"Mood: {request.project.mood}."
    camera = scene.camera_phrase() if scene else "locked-off camera"
    ref_line = ", ".join(f.label for f in bound.images if f.label)
    if ref_line:
        extra = f"{extra} Match {ref_line}.".strip()
    names = ", ".join(dict.fromkeys(f.root.name for f in bound.files))
    if names and names.lower() not in performance.lower():
        extra = f"{extra} Characters: {names}.".strip()
    return (
        f"Subject: {subject}. {performance}\n"
        f"Performance: {performance}\n"
        f"Ambience: cinematic lighting that matches the story mood\n"
        f"Camera: {camera}\n"
        f"Extra: {extra} Photoreal, coherent motion, no morphing."
    )
