"""Project document and JSON persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from moviemaker.core.asset import Asset, ensure_asset_handles
from moviemaker.core.hardware import HardwareProfile
from moviemaker.core.scene import Scene
from moviemaker.core.timeline import TimelineLayer, default_layers, reflow_video_clips

PROJECT_FILENAME = "project.json"
ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
GENERATE_QUALITIES = ["sd", "hd", "fhd"]
EXPORT_QUALITIES = ["hd", "fhd", "4k"]
PRESETS: dict[str, dict[str, Any]] = {
    "blank": {
        "label": "Blank",
        "mood": "",
        "base_storyline": "",
        "aspect_ratio": "16:9",
        "target_length_seconds": 30,
    },
    "ad": {
        "label": "Advertisement",
        "mood": "polished, high-energy, product-forward",
        "base_storyline": "A 20-second product ad: hook, benefit, proof, call to action.",
        "aspect_ratio": "9:16",
        "target_length_seconds": 20,
    },
    "short_film": {
        "label": "Short film",
        "mood": "cinematic, character-driven, natural light",
        "base_storyline": "A short character piece with a beginning, a turn, and a quiet ending.",
        "aspect_ratio": "16:9",
        "target_length_seconds": 90,
    },
    "product_demo": {
        "label": "Product demo",
        "mood": "clean, instructional, premium",
        "base_storyline": "Show the product in use: problem, demo, close-up details, result.",
        "aspect_ratio": "16:9",
        "target_length_seconds": 40,
    },
    "music_video": {
        "label": "Music video",
        "mood": "stylized, rhythmic, bold color",
        "base_storyline": "Picture-driven cuts that follow a song: verse, chorus, verse, finale.",
        "aspect_ratio": "16:9",
        "target_length_seconds": 60,
    },
}


class Project(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    project_dir: str
    mood: str = ""
    base_storyline: str = ""
    aspect_ratio: str = "16:9"
    target_length_seconds: float = 30.0
    fps: float = 24.0
    default_model_id: str = "minimax_h3"
    default_model_type: str | None = None
    default_model_options: dict[str, Any] = Field(default_factory=dict)
    generate_quality: str = "sd"
    export_quality: str = "hd"
    upscale_enabled: bool = False
    upscale_method: str = ""
    hardware_profile_snapshot: HardwareProfile | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    assets: list[Asset] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    layers: list[TimelineLayer] = Field(default_factory=default_layers)
    preset: str = "blank"

    def dir(self) -> Path:
        return Path(self.project_dir)

    def clips_dir(self) -> Path:
        path = self.dir() / "clips"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def assets_dir(self) -> Path:
        path = self.dir() / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def export_dir(self) -> Path:
        path = self.dir() / "export"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def logs_dir(self) -> Path:
        path = self.dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def tmp_dir(self) -> Path:
        path = self.dir() / "tmp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_scene(self, scene_id: str) -> Scene | None:
        return next((s for s in self.scenes if s.id == scene_id), None)

    def get_asset(self, asset_id: str) -> Asset | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def video_layer(self) -> TimelineLayer:
        for layer in self.layers:
            if layer.type == "video":
                return layer
        layer = TimelineLayer(id="video_1", name="Video", type="video")
        self.layers.insert(0, layer)
        return layer

    def sync_timeline(self) -> None:
        reflow_video_clips(self.video_layer(), self.scenes)

    def total_duration(self) -> float:
        if self.scenes:
            last = self.scenes[-1]
            return last.start_time_seconds + last.duration_seconds
        return 0.0


def _ensure_layout(root: Path) -> None:
    for name in ("assets", "clips", "export", "logs", "tmp"):
        (root / name).mkdir(parents=True, exist_ok=True)


def create_project(
    folder: Path,
    name: str,
    *,
    mood: str = "",
    base_storyline: str = "",
    aspect_ratio: str = "16:9",
    target_length_seconds: float = 30.0,
    default_model_id: str = "minimax_h3",
    hardware: HardwareProfile | None = None,
    preset: str = "blank",
) -> Project:
    folder = folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    existing = folder / PROJECT_FILENAME
    if existing.exists():
        raise FileExistsError(f"A project already exists in {folder}")
    _ensure_layout(folder)
    preset_data = PRESETS.get(preset, PRESETS["blank"])
    project = Project(
        name=name,
        project_dir=str(folder),
        mood=mood or preset_data["mood"],
        base_storyline=base_storyline or preset_data["base_storyline"],
        aspect_ratio=aspect_ratio or preset_data["aspect_ratio"],
        target_length_seconds=target_length_seconds or preset_data["target_length_seconds"],
        default_model_id=default_model_id,
        hardware_profile_snapshot=hardware,
        preset=preset,
    )
    save_project(project)
    return project


def save_project(project: Project) -> Path:
    project.touch()
    project.sync_timeline()
    ensure_asset_handles(project.assets)
    root = project.dir()
    _ensure_layout(root)
    path = root / PROJECT_FILENAME
    payload = project.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_project(folder: Path) -> Project:
    folder = folder.expanduser().resolve()
    path = folder / PROJECT_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"No {PROJECT_FILENAME} in {folder}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["project_dir"] = str(folder)
    project = Project.model_validate(data)
    ensure_asset_handles(project.assets)
    _ensure_layout(folder)
    project.sync_timeline()
    return project
