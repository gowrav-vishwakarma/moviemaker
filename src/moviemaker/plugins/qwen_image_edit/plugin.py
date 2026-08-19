"""Qwen Image Edit (instruction + multi-reference) plugin."""

from __future__ import annotations

from typing import Any

from moviemaker.plugins.base import Capability, GenerationRequest, VramTier
from moviemaker.plugins.options_schema import COMMON_IMAGE_FIELDS
from moviemaker.plugins.qwen_image_edit.prompt_builder import build_qwen_prompt
from moviemaker.plugins.qwen_image_edit.settings_map import map_qwen_settings
from moviemaker.plugins.reference import image_contract
from moviemaker.plugins.runner import BasePlugin

TIERS = [
    VramTier(16, 24, "Fast", "bf16", "qwen_image_edit_plus_20B", "Edit Plus 20B"),
    VramTier(10, 16, "Standard", "int8", "qwen_image_edit_plus_20B", "Edit Plus INT8"),
    VramTier(8, 12, "Low-VRAM", "int8", "qwen_image_edit_20B", "Edit 20B INT8"),
    VramTier(0, 8, "CPU", "int8", "qwen_image_20B", "Qwen Image generate + offload"),
]


class QwenImageEditPlugin(BasePlugin):
    id = "qwen_image_edit"

    def __init__(self) -> None:
        self.capabilities = Capability(
            name="Qwen Image Edit",
            kind="image",
            description="Instruction image editing and generation with strong text rendering.",
            architectures=[
                "qwen_image_edit_plus_20B",
                "qwen_image_edit_20B",
                "qwen_image_20B",
                "qwen_image_2512_20B",
                "qwen_image_layered_20B",
            ],
            supported_ratios=["1:1", "16:9", "9:16", "4:3"],
            min_duration_seconds=0,
            max_duration_seconds=0,
            duration_step_seconds=0,
            resolutions=["1024x1024", "1328x1328", "1664x928", "928x1664"],
            supports_negative_prompt=True,
            supports_image_input=True,
            supports_video_input=False,
            supports_audio_input=False,
            supports_extend=False,
            max_reference_images=6,
            supports_lora=True,
            default_options={"num_inference_steps": 20, "guidance_scale": 4.0, "seed": -1},
            options_schema=list(COMMON_IMAGE_FIELDS),
            vram_tiers=TIERS,
            prompt_style_id="qwen_instruct",
            reference=image_contract(max_images=6),
            preferred_prompt_length="short",
        )

    def build_prompt(self, request: GenerationRequest) -> str:
        return build_qwen_prompt(request)

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]:
        request.kind = "image"
        request.negative_prompt = self.build_negative_prompt(request)
        return map_qwen_settings(request, prompt, self.catalog)
