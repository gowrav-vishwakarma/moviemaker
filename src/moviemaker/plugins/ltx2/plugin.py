"""LTX-2.3 / LTX-2 video plugin."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import Capability, GenerationRequest, VramTier
from moviemaker.plugins.ltx2.prompt_builder import build_ltx_prompt
from moviemaker.plugins.ltx2.settings_map import map_ltx_settings
from moviemaker.plugins.options_schema import COMMON_VIDEO_FIELDS
from moviemaker.plugins.reference import ltx_contract
from moviemaker.plugins.runner import BasePlugin

TIERS = [
    VramTier(18, 24, "Fast", "bf16", "ltx2_22B_distilled", "22B distilled bf16"),
    VramTier(12, 16, "Standard", "int8", "ltx2_22B_distilled", "22B distilled INT8"),
    VramTier(8, 12, "Low-VRAM", "gguf_q8", "ltx2_22B_distilled_gguf_q8_0", "GGUF Q8"),
    VramTier(0, 8, "CPU", "gguf_q4", "ltx2_22B_distilled_gguf_q4_k_m", "GGUF Q4"),
]


class Ltx2Plugin(BasePlugin):
    id = "ltx2"

    def __init__(self) -> None:
        self.capabilities = Capability(
            name="LTX-2",
            kind="video",
            description="LTX-2.3 long-form video with optional soundtrack and keyframes.",
            architectures=["ltx2_22B", "ltx2_distilled", "ltxv"],
            supported_ratios=["16:9", "9:16"],
            min_duration_seconds=2,
            max_duration_seconds=20,
            duration_step_seconds=1,
            resolutions=["1280x720", "1920x1080", "720x1280"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=True,
            supports_audio_input=True,
            supports_extend=True,
            max_reference_images=2,
            supports_lora=True,
            default_options={"num_inference_steps": 8, "guidance_scale": 1.0, "seed": -1},
            options_schema=list(COMMON_VIDEO_FIELDS),
            vram_tiers=TIERS,
            prompt_style_id="ltx_natural",
            reference=ltx_contract(),
            preferred_prompt_length="short",
            fps=24.0,
        )

    def build_prompt(self, request: GenerationRequest) -> str:
        return build_ltx_prompt(request)

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]:
        request.negative_prompt = self.build_negative_prompt(request)
        return map_ltx_settings(request, prompt, self.catalog)
