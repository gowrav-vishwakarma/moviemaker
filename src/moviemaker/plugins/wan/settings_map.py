"""Wan scene -> Wan2GP settings."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.settings_common import apply_catalog_defaults, base_settings


def map_wan_settings(request: GenerationRequest, prompt: str, catalog: Any) -> dict[str, Any]:
    settings = base_settings(request, prompt, fps=16.0)
    settings.setdefault("guidance_scale", 4.0)
    settings.setdefault("flow_shift", 12)
    return apply_catalog_defaults(settings, catalog, request.model_type)
