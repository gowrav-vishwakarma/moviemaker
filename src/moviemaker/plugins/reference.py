"""What a model accepts as references, labels, and recommended upscalers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MediaKind = Literal["image", "video", "audio"]
LabelKind = Literal["subject", "picture", "video", "audio", "name"]


@dataclass
class ReferenceContract:
    subject_label: str | None = None
    picture_label: str | None = "Image {n}"
    video_label: str | None = None
    audio_label: str | None = None
    max_images: int = 4
    max_videos: int = 0
    max_audio: int = 0
    max_total: int = 8
    image_roles: list[str] = field(
        default_factory=lambda: ["identity", "first_frame", "last_frame", "wardrobe", "pose", "background", "style"]
    )
    video_roles: list[str] = field(default_factory=list)
    audio_roles: list[str] = field(default_factory=list)
    wan2gp_image_key: str = "image_refs"
    wan2gp_video_key: str = "video_guide"
    wan2gp_audio_key: str = "audio_guide"
    file_order: tuple[str, ...] = ("image", "video", "audio")
    recommended_upscalers: list[str] = field(default_factory=lambda: ["lanczos2"])
    recommended_generate_quality: str = "hd"
    supports_native_high_res: bool = True
    uses_subject_labels: bool = False
    uses_display_names: bool = False

    def format_label(self, kind: LabelKind, index: int) -> str:
        if kind == "name":
            return ""
        template = {
            "subject": self.subject_label,
            "picture": self.picture_label,
            "video": self.video_label,
            "audio": self.audio_label,
        }.get(kind)
        if not template:
            return ""
        return template.format(n=index)

    @property
    def syntax_hint(self) -> str:
        if self.uses_display_names:
            return "asset name"
        if self.uses_subject_labels and self.subject_label:
            return self.format_label("subject", 1)
        if self.picture_label:
            return self.format_label("picture", 1)
        return "Image 1"


def h3_contract() -> ReferenceContract:
    return ReferenceContract(
        subject_label="<Subject {n}>",
        picture_label="<Picture {n}>",
        video_label="<Video {n}>",
        audio_label="<Audio {n}>",
        max_images=9,
        max_videos=3,
        max_audio=3,
        max_total=12,
        image_roles=["identity", "first_frame", "last_frame", "wardrobe", "pose", "background", "style"],
        video_roles=["camera", "motion", "identity", "edit_source"],
        audio_roles=["voice", "bed", "copy"],
        wan2gp_image_key="image_refs",
        wan2gp_video_key="video_source",
        wan2gp_audio_key="audio_guide",
        recommended_upscalers=["seedvr22", "flashvsr2", "lanczos2"],
        recommended_generate_quality="sd",
        supports_native_high_res=True,
        uses_subject_labels=True,
    )


def wan_contract() -> ReferenceContract:
    return ReferenceContract(
        subject_label=None,
        picture_label="Image{n}",
        video_label=None,
        audio_label=None,
        max_images=2,
        max_videos=1,
        max_audio=0,
        max_total=3,
        image_roles=["identity", "first_frame", "last_frame", "background"],
        video_roles=["pose", "depth", "motion", "camera"],
        wan2gp_image_key="image_refs",
        wan2gp_video_key="video_guide",
        recommended_upscalers=["seedvr22", "flashvsr2", "lanczos2"],
        recommended_generate_quality="sd",
        supports_native_high_res=True,
    )


def ltx_contract() -> ReferenceContract:
    return ReferenceContract(
        subject_label=None,
        picture_label=None,
        video_label=None,
        audio_label=None,
        max_images=2,
        max_videos=1,
        max_audio=1,
        max_total=3,
        image_roles=["identity", "first_frame", "last_frame"],
        video_roles=["motion", "camera"],
        audio_roles=["voice", "bed"],
        wan2gp_image_key="image_refs",
        wan2gp_video_key="video_source",
        wan2gp_audio_key="audio_guide",
        recommended_upscalers=["seedvr22", "lanczos2"],
        recommended_generate_quality="hd",
        uses_display_names=True,
    )


def image_contract(*, max_images: int = 4) -> ReferenceContract:
    return ReferenceContract(
        subject_label=None,
        picture_label="Image {n}",
        video_label=None,
        audio_label=None,
        max_images=max_images,
        max_videos=0,
        max_audio=0,
        max_total=max_images,
        image_roles=["identity", "style", "background"],
        recommended_upscalers=["lanczos2", "seedvr22"],
        recommended_generate_quality="hd",
    )


def generic_contract() -> ReferenceContract:
    return ReferenceContract(
        subject_label=None,
        picture_label="Image {n}",
        video_label="Video {n}",
        audio_label="Audio {n}",
        max_images=8,
        max_videos=2,
        max_audio=2,
        max_total=10,
        image_roles=["identity", "first_frame", "last_frame", "background", "style"],
        video_roles=["camera", "motion", "edit_source"],
        audio_roles=["voice", "bed"],
        recommended_upscalers=["lanczos2", "seedvr22", "flashvsr2"],
        recommended_generate_quality="hd",
    )
