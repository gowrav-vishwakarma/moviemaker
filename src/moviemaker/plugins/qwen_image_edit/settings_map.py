"""Qwen Image Edit -> Wan2GP settings."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.settings_common import apply_catalog_defaults, base_settings


def map_qwen_settings(request: GenerationRequest, prompt: str, catalog: Any) -> dict[str, Any]:
    settings = base_settings(request, prompt, fps=1.0)
    settings["batch_size"] = 1
    settings.setdefault("num_inference_steps", 20)
    settings.setdefault("resolution", "1024x1024")
    return apply_catalog_defaults(settings, catalog, request.model_type)
