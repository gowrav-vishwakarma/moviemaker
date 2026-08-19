"""Plugin protocols, capabilities, and generation request/result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from moviemaker.core.asset import Asset
from moviemaker.core.hardware import HardwareProfile
from moviemaker.core.project import Project
from moviemaker.core.scene import Scene
from moviemaker.plugins.reference import ReferenceContract

PluginKind = Literal["video", "image"]
JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


@dataclass
class VramTier:
    min_vram_gb: int
    recommended_vram_gb: int
    label: str
    quantization: str | None
    model_type: str
    notes: str = ""


@dataclass
class Capability:
    name: str
    kind: PluginKind
    description: str
    architectures: list[str]
    supported_ratios: list[str]
    min_duration_seconds: int
    max_duration_seconds: int
    duration_step_seconds: int
    resolutions: list[str]
    supports_negative_prompt: bool
    supports_image_input: bool
    supports_video_input: bool
    supports_audio_input: bool
    supports_extend: bool
    max_reference_images: int
    supports_lora: bool
    default_options: dict[str, Any]
    options_schema: list[dict[str, Any]]
    vram_tiers: list[VramTier]
    prompt_style_id: str
    reference: ReferenceContract = field(default_factory=ReferenceContract)
    preferred_prompt_length: str = "medium"
    fps: float = 24.0

    @property
    def reference_syntax(self) -> str:
        return self.reference.syntax_hint


@dataclass
class GenerationRequest:
    project: Project
    scene: Scene | None
    assets: list[Asset]
    output_dir: Path
    hardware_profile: HardwareProfile
    options: dict[str, Any]
    model_type: str
    quantization: str | None
    prompt: str = ""
    negative_prompt: str | None = None
    reference_paths: list[Path] = field(default_factory=list)
    kind: PluginKind = "video"
    dry_run: bool = False
    log_path: Path | None = None
    cancel_event: Any | None = None
    on_progress: Any | None = None
    bound: Any | None = None


@dataclass
class GenerationResult:
    status: JobStatus
    video_path: Path | None = None
    audio_path: Path | None = None
    image_path: Path | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None
    log_text: str = ""


@runtime_checkable
class ModelPlugin(Protocol):
    id: str
    capabilities: Capability

    def is_available(self, hardware: HardwareProfile, catalog: Any) -> bool: ...

    def select_tier(self, hardware: HardwareProfile) -> VramTier: ...

    def build_prompt(self, request: GenerationRequest) -> str: ...

    def build_negative_prompt(self, request: GenerationRequest) -> str | None: ...

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]: ...

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def extend(self, existing: Path, request: GenerationRequest) -> GenerationResult: ...
