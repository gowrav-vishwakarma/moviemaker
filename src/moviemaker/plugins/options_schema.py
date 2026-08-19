"""Option field helpers for dynamic plugin UI forms."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FieldType = Literal["int", "float", "str", "bool", "select", "lora", "seed", "textarea"]


class OptionField(BaseModel):
    key: str
    label: str
    type: FieldType = "str"
    default: Any = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None
    help: str = ""
    advanced: bool = False


def field_dict(
    key: str,
    label: str,
    type: FieldType = "str",
    default: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return OptionField(key=key, label=label, type=type, default=default, **kwargs).model_dump()


COMMON_VIDEO_FIELDS: list[dict[str, Any]] = [
    field_dict("num_inference_steps", "Steps", "int", 8, min=1, max=50, step=1),
    field_dict("guidance_scale", "Guidance", "float", 1.0, min=0, max=15, step=0.1),
    field_dict("seed", "Seed", "seed", -1, min=-1, max=2_147_483_647, step=1, help="-1 = random"),
    field_dict("resolution", "Resolution", "select", "1280x720", options=["832x480", "1280x720", "1920x1080"]),
    field_dict("activated_loras", "LoRA", "lora", ""),
    field_dict("loras_multipliers", "LoRA weight", "str", "1.0", advanced=True),
]

COMMON_IMAGE_FIELDS: list[dict[str, Any]] = [
    field_dict("num_inference_steps", "Steps", "int", 20, min=1, max=50, step=1),
    field_dict("guidance_scale", "Guidance", "float", 3.5, min=0, max=15, step=0.1),
    field_dict("seed", "Seed", "seed", -1, min=-1, max=2_147_483_647, step=1),
    field_dict("resolution", "Size", "select", "1024x1024", options=["1024x1024", "1280x720", "720x1280", "1328x1328"]),
    field_dict("activated_loras", "LoRA", "lora", ""),
    field_dict("loras_multipliers", "LoRA weight", "str", "1.0", advanced=True),
]
