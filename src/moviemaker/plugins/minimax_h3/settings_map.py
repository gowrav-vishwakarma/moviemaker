"""Map a Scene onto MiniMax H3 Wan2GP settings (FL2VA or Ref2VA)."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import h3_contract
from moviemaker.plugins.settings_common import apply_catalog_defaults, base_settings
from moviemaker.plugins.tagging import ensure_bound


def _prefer_ref2va(request: GenerationRequest, catalog: Any) -> None:
    bound = ensure_bound(request, h3_contract(), strict=False)
    if not bound.has_identity_refs() and not bound.videos and not bound.audios:
        return
    current = request.model_type or ""
    if "ref2va" in current:
        return
    if "fl2va" not in current:
        return
    alt = current.replace("fl2va", "ref2va")
    if catalog is not None and catalog.get(alt):
        request.model_type = alt


def map_minimax_settings(request: GenerationRequest, prompt: str, catalog: Any) -> dict[str, Any]:
    _prefer_ref2va(request, catalog)
    settings = base_settings(request, prompt, fps=24.0)
    settings.setdefault("num_inference_steps", 8)
    return apply_catalog_defaults(settings, catalog, request.model_type)
