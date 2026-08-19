"""Generic plugin wrapping any catalog architecture without a dedicated expert."""

from __future__ import annotations

from typing import Any

from moviemaker.core.hardware import HardwareProfile
from moviemaker.plugins.base import Capability, GenerationRequest, VramTier
from moviemaker.plugins.options_schema import COMMON_IMAGE_FIELDS, COMMON_VIDEO_FIELDS
from moviemaker.plugins.generic.prompt_builder import build_generic_prompt
from moviemaker.plugins.reference import generic_contract, image_contract
from moviemaker.plugins.runner import BasePlugin


GENERIC_TIERS = [
    VramTier(24, 24, "Fast", "bf16", "", "Full precision when VRAM allows"),
    VramTier(12, 16, "Standard", "int8", "", "INT8 quantization"),
    VramTier(6, 10, "Low-VRAM", "int8", "", "INT8 + offload"),
    VramTier(0, 6, "CPU", "int8", "", "Aggressive offload"),
]


class GenericPlugin(BasePlugin):
    id = "generic"

    def __init__(self) -> None:
        self.capabilities = Capability(
            name="Generic (Wan2GP passthrough)",
            kind="video",
            description="Use any Wan2GP model that does not have a dedicated plugin.",
            architectures=[],
            supported_ratios=["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            min_duration_seconds=1,
            max_duration_seconds=20,
            duration_step_seconds=1,
            resolutions=["832x480", "1280x720", "1920x1080"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=True,
            supports_audio_input=True,
            supports_extend=True,
            max_reference_images=8,
            supports_lora=True,
            default_options={"num_inference_steps": 8, "guidance_scale": 1.0, "seed": -1},
            options_schema=list(COMMON_VIDEO_FIELDS),
            vram_tiers=list(GENERIC_TIERS),
            prompt_style_id="generic",
            reference=generic_contract(),
            preferred_prompt_length="medium",
        )

    def capabilities_for(self, architecture: str, image: bool = False) -> Capability:
        cap = self.capabilities
        return Capability(
            name=cap.name,
            kind="image" if image else "video",
            description=cap.description,
            architectures=[architecture] if architecture else [],
            supported_ratios=cap.supported_ratios,
            min_duration_seconds=0 if image else cap.min_duration_seconds,
            max_duration_seconds=0 if image else cap.max_duration_seconds,
            duration_step_seconds=cap.duration_step_seconds,
            resolutions=cap.resolutions if not image else ["1024x1024", "1280x720", "720x1280"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=not image,
            supports_audio_input=not image,
            supports_extend=not image,
            max_reference_images=8,
            supports_lora=True,
            default_options=dict(cap.default_options),
            options_schema=list(COMMON_IMAGE_FIELDS if image else COMMON_VIDEO_FIELDS),
            vram_tiers=list(GENERIC_TIERS),
            prompt_style_id="generic",
            reference=image_contract(max_images=8) if image else generic_contract(),
            preferred_prompt_length="medium",
        )

    def is_available(self, hardware: HardwareProfile, catalog: Any) -> bool:
        return True

    def select_tier(self, hardware: HardwareProfile) -> VramTier:
        tier = super().select_tier(hardware)
        if self.catalog:
            # keep quantization, leave model_type to the scene override / catalog pick
            return VramTier(
                min_vram_gb=tier.min_vram_gb,
                recommended_vram_gb=tier.recommended_vram_gb,
                label=tier.label,
                quantization=tier.quantization,
                model_type=tier.model_type,
                notes=tier.notes,
            )
        return tier

    def build_prompt(self, request: GenerationRequest) -> str:
        return build_generic_prompt(request) or request.prompt
