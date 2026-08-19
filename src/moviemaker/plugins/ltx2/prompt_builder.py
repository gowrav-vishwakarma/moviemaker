"""LTX-2 natural-language prompt builder."""

from __future__ import annotations

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import ltx_contract
from moviemaker.plugins.tagging import ensure_bound


def build_ltx_prompt(request: GenerationRequest) -> str:
    bound = ensure_bound(request, ltx_contract(), strict=False)
    scene = request.scene
    body = (bound.rewritten or request.prompt or (scene.prompt if scene else "") or (scene.plot_summary if scene else "")).strip()
    camera = scene.camera_phrase() if scene else ""
    mood = request.project.mood
    bits = [body]
    if camera and "camera" not in body.lower():
        bits.append(f"The camera: {camera}.")
    if mood and mood.lower() not in body.lower():
        bits.append(f"Tone: {mood}.")
    names = [f.root.name for f in bound.files]
    for name in dict.fromkeys(names):
        if name and name.lower() not in body.lower():
            bits.append(f"{name} remains visually consistent.")
    return " ".join(b for b in bits if b)
