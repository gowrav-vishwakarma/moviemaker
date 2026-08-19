"""Timeline layers and clips."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

LayerType = Literal["video", "audio", "image"]


class Clip(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    scene_id: str | None = None
    asset_id: str | None = None
    start_time_seconds: float = 0.0
    duration_seconds: float = 5.0
    trim_start: float = 0.0
    trim_end: float = 0.0
    volume: float = 1.0
    label: str = ""

    @property
    def effective_duration(self) -> float:
        extra = self.trim_start + self.trim_end
        return max(0.1, self.duration_seconds - extra)

    @property
    def end_time_seconds(self) -> float:
        return self.start_time_seconds + self.effective_duration


class TimelineLayer(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str
    type: LayerType
    clips: list[Clip] = Field(default_factory=list)
    muted: bool = False
    visible: bool = True

    def total_duration(self) -> float:
        if not self.clips:
            return 0.0
        return max(c.end_time_seconds for c in self.clips)


def default_layers() -> list[TimelineLayer]:
    return [
        TimelineLayer(id="video_1", name="Video", type="video"),
        TimelineLayer(id="audio_1", name="Dialogue / SFX", type="audio"),
        TimelineLayer(id="audio_2", name="Music", type="audio"),
        TimelineLayer(id="image_1", name="Overlays / Stills", type="image"),
    ]


def reflow_video_clips(layer: TimelineLayer, scenes: list[Any]) -> None:
    """Keep video-layer clips aligned with scene order and durations."""
    by_scene = {c.scene_id: c for c in layer.clips if c.scene_id}
    new_clips: list[Clip] = []
    cursor = 0.0
    for scene in scenes:
        clip = by_scene.get(scene.id)
        if clip is None:
            clip = Clip(
                scene_id=scene.id,
                start_time_seconds=cursor,
                duration_seconds=scene.duration_seconds,
                label=scene.title,
            )
        else:
            clip.start_time_seconds = cursor
            clip.duration_seconds = scene.duration_seconds
            clip.label = scene.title
        new_clips.append(clip)
        cursor += scene.duration_seconds
        scene.start_time_seconds = clip.start_time_seconds
    layer.clips = new_clips
