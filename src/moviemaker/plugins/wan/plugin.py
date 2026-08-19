"""Wan 2.1 / 2.2 video plugin."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import Capability, GenerationRequest, VramTier
from moviemaker.plugins.options_schema import COMMON_VIDEO_FIELDS, field_dict
from moviemaker.plugins.reference import wan_contract
from moviemaker.plugins.runner import BasePlugin
from moviemaker.plugins.wan.prompt_builder import build_wan_prompt
from moviemaker.plugins.wan.settings_map import map_wan_settings

TIERS = [
    VramTier(16, 24, "Fast", "bf16", "t2v_2_2", "Wan 2.2 14B bf16"),
    VramTier(10, 16, "Standard", "int8", "t2v_2_2", "Wan 2.2 14B INT8"),
    VramTier(6, 10, "Low-VRAM", "int8", "t2v_1.3B", "Wan 1.3B INT8"),
    VramTier(0, 6, "CPU", "int8", "t2v_1.3B", "1.3B + offload"),
]


class WanPlugin(BasePlugin):
    id = "wan"

    def __init__(self) -> None:
        self.capabilities = Capability(
            name="Wan",
            kind="video",
            description="Wan 2.1/2.2 text-to-video and image-to-video family.",
            architectures=[
                "t2v",
                "t2v_2_2",
                "t2v_1.3B",
                "i2v",
                "i2v_2_2",
                "ti2v_2_2",
                "t2v_fusionix",
            ],
            supported_ratios=["16:9", "9:16", "1:1"],
            min_duration_seconds=2,
            max_duration_seconds=10,
            duration_step_seconds=1,
            resolutions=["832x480", "1280x720"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=True,
            supports_audio_input=False,
            supports_extend=True,
            max_reference_images=2,
            supports_lora=True,
            default_options={"num_inference_steps": 8, "guidance_scale": 4.0, "flow_shift": 12, "seed": -1},
            options_schema=COMMON_VIDEO_FIELDS
            + [field_dict("flow_shift", "Flow shift", "float", 12, min=1, max=20, step=0.5, advanced=True)],
            vram_tiers=TIERS,
            prompt_style_id="wan_space",
            reference=wan_contract(),
            preferred_prompt_length="medium",
            fps=16.0,
        )

    def build_prompt(self, request: GenerationRequest) -> str:
        return build_wan_prompt(request)

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]:
        request.negative_prompt = self.build_negative_prompt(request)
        settings = map_wan_settings(request, prompt, self.catalog)
        if request.options.get("flow_shift") is not None:
            settings["flow_shift"] = float(request.options["flow_shift"])
        return settings
