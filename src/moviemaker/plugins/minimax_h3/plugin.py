"""MiniMax H3 plugin: FL2VA first, hardware-adaptive bf16 / int8 / pruned."""

from __future__ import annotations

from typing import Any

from moviemaker.core.hardware import HardwareProfile
from moviemaker.plugins.base import Capability, GenerationRequest, VramTier
from moviemaker.plugins.minimax_h3.prompt_builder import build_minimax_prompt
from moviemaker.plugins.minimax_h3.settings_map import map_minimax_settings
from moviemaker.plugins.options_schema import COMMON_VIDEO_FIELDS, field_dict
from moviemaker.plugins.reference import h3_contract
from moviemaker.plugins.runner import BasePlugin


TIERS = [
    VramTier(20, 24, "Fast", "bf16", "minimax_h3_fl2va", "33B bf16 FL2VA"),
    VramTier(12, 16, "Standard", "int8", "minimax_h3_fl2va", "33B INT8 ConvRot"),
    VramTier(8, 12, "Low-VRAM", "int8", "minimax_h3_fl2va_pruned", "Pruned 20B INT8"),
    VramTier(0, 8, "CPU", "int8", "minimax_h3_fl2va_pruned", "Pruned + heavy offload"),
]


class MiniMaxH3Plugin(BasePlugin):
    id = "minimax_h3"

    def __init__(self) -> None:
        self.capabilities = Capability(
            name="MiniMax H3",
            kind="video",
            description="First/last-frame to synchronized video and stereo audio.",
            architectures=["minimax_h3_fl2va", "minimax_h3_fl2va_pruned", "minimax_h3_ref2va", "minimax_h3_ref2va_pruned"],
            supported_ratios=["16:9", "9:16", "1:1"],
            min_duration_seconds=2,
            max_duration_seconds=15,
            duration_step_seconds=1,
            resolutions=["1280x720", "720x1280", "960x960"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=True,
            supports_audio_input=True,
            supports_extend=False,
            max_reference_images=9,
            supports_lora=False,
            default_options={"num_inference_steps": 8, "guidance_scale": 1.0, "seed": -1},
            options_schema=COMMON_VIDEO_FIELDS
            + [
                field_dict(
                    "audio_direction",
                    "Audio notes",
                    "textarea",
                    "natural room tone, clear vocals",
                    help="Merged into the MiniMax audio block",
                )
            ],
            vram_tiers=TIERS,
            prompt_style_id="minimax_timed_shots",
            reference=h3_contract(),
            preferred_prompt_length="long",
            fps=24.0,
        )

    def select_tier(self, hardware: HardwareProfile) -> VramTier:
        return super().select_tier(hardware)

    def build_prompt(self, request: GenerationRequest) -> str:
        extra = request.options.get("audio_direction")
        prompt = build_minimax_prompt(request)
        if extra:
            prompt += f"\n\nAudio notes: {extra}"
        return prompt

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]:
        request.negative_prompt = self.build_negative_prompt(request)
        return map_minimax_settings(request, prompt, self.catalog)
