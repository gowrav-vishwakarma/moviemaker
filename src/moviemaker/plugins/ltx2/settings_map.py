"""LTX-2 scene -> Wan2GP settings."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.settings_common import apply_catalog_defaults, base_settings


def map_ltx_settings(request: GenerationRequest, prompt: str, catalog: Any) -> dict[str, Any]:
    settings = base_settings(request, prompt, fps=24.0)
    if request.scene:
        settings["camera_motion"] = request.scene.camera_motion
    settings.setdefault("num_inference_steps", 8)
    return apply_catalog_defaults(settings, catalog, request.model_type)
