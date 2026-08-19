"""Flux image-generation / Kontext-edit plugin."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import Capability, GenerationRequest, VramTier
from moviemaker.plugins.flux.prompt_builder import build_flux_prompt
from moviemaker.plugins.flux.settings_map import map_flux_settings
from moviemaker.plugins.options_schema import COMMON_IMAGE_FIELDS
from moviemaker.plugins.reference import image_contract
from moviemaker.plugins.runner import BasePlugin

TIERS = [
    VramTier(16, 24, "Fast", "bf16", "flux_krea", "Flux Dev / Krea bf16"),
    VramTier(10, 16, "Standard", "int8", "flux_krea", "Flux INT8"),
    VramTier(6, 10, "Low-VRAM", "int8", "flux2_klein_base_4b", "Klein 4B"),
    VramTier(0, 6, "CPU", "int8", "flux2_klein_base_4b", "Klein 4B offload"),
]


class FluxPlugin(BasePlugin):
    id = "flux"

    def __init__(self) -> None:
        self.capabilities = Capability(
            name="Flux",
            kind="image",
            description="FLUX image generation and instruction editing (Kontext, Krea, Klein).",
            architectures=["flux", "flux_dev_kontext", "flux_krea", "flux2_dev", "flux2_klein_9b", "flux2_klein_base_4b", "pi_flux2"],
            supported_ratios=["16:9", "9:16", "1:1", "4:3"],
            min_duration_seconds=0,
            max_duration_seconds=0,
            duration_step_seconds=0,
            resolutions=["1024x1024", "1280x720", "720x1280", "1328x1328"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=False,
            supports_audio_input=False,
            supports_extend=False,
            max_reference_images=4,
            supports_lora=True,
            default_options={"num_inference_steps": 20, "guidance_scale": 3.5, "seed": -1},
            options_schema=list(COMMON_IMAGE_FIELDS),
            vram_tiers=TIERS,
            prompt_style_id="flux",
            reference=image_contract(max_images=4),
            preferred_prompt_length="short",
        )

    def build_prompt(self, request: GenerationRequest) -> str:
        return build_flux_prompt(request)

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]:
        request.kind = "image"
        request.negative_prompt = self.build_negative_prompt(request)
        return map_flux_settings(request, prompt, self.catalog)
