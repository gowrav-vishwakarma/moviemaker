"""Scene model and camera presets."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

SceneStatus = Literal["draft", "queued", "generating", "done", "failed", "cancelled"]
AssetRole = Literal[
    "first_frame",
    "last_frame",
    "subject",
    "prop",
    "background",
    "style",
    "motion",
    "audio",
    "reference",
    "camera",
    "pose",
    "edit_source",
    "wardrobe",
]

CAMERA_PRESETS: dict[str, str] = {
    "static": "locked-off camera, no movement",
    "dolly_in": "slow dolly in toward the subject",
    "pull_back": "camera pulls back, revealing more of the environment",
    "orbit": "camera slowly orbits the subject",
    "pan_left": "smooth pan left",
    "pan_right": "smooth pan right",
    "tilt_up": "camera tilts up",
    "tilt_down": "camera tilts down",
    "tracking": "tracking shot following the subject",
    "crane_up": "crane up, rising above the scene",
    "crane_down": "crane down toward the subject",
    "handheld": "subtle handheld camera, lived-in documentary feel",
    "gimbal_walk": "smooth gimbal walk-through",
    "push_in": "gentle push-in on the face",
    "whip_pan": "fast whip pan to the next beat",
}

CAMERA_SPEEDS: dict[str, str] = {
    "slow": "slow, measured movement",
    "moderate": "moderate, cinematic pacing",
    "fast": "fast, energetic movement",
    "creeping": "barely perceptible creeping move",
    "rapid": "rapid, high-energy motion",
}


class AssetRef(BaseModel):
    asset_id: str
    role: AssetRole = "reference"
    slot: int = 1


class Scene(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    title: str = "Untitled scene"
    plot_summary: str = ""
    start_time_seconds: float = 0.0
    duration_seconds: float = 5.0
    prompt: str = ""
    negative_prompt: str = ""
    model_id: str = "generic"
    model_type_override: str | None = None
    quantization_override: str | None = None
    model_options_override: dict[str, Any] = Field(default_factory=dict)
    asset_refs: list[AssetRef] = Field(default_factory=list)
    camera_motion: str = "static"
    camera_speed: str = "moderate"
    camera_custom: str = ""
    status: SceneStatus = "draft"
    output_path: str | None = None
    audio_output_path: str | None = None
    error: str | None = None
    generation_log: str = ""

    def camera_phrase(self) -> str:
        base = CAMERA_PRESETS.get(self.camera_motion, self.camera_motion.replace("_", " "))
        speed = CAMERA_SPEEDS.get(self.camera_speed, "")
        parts = [p for p in (base, speed, self.camera_custom.strip()) if p]
        return ", ".join(parts)
