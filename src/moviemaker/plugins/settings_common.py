"""Shared Wan2GP settings mapping helpers used by every plugin."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from moviemaker.core.project import Project
from moviemaker.core.scene import Scene
from moviemaker.plugins.base import GenerationRequest


ASPECT_RESOLUTIONS: dict[str, dict[str, str]] = {
    "16:9": {"sd": "832x480", "hd": "1280x720", "fhd": "1920x1080", "4k": "3840x2160"},
    "9:16": {"sd": "480x832", "hd": "720x1280", "fhd": "1080x1920", "4k": "2160x3840"},
    "1:1": {"sd": "720x720", "hd": "1024x1024", "fhd": "1328x1328", "4k": "2048x2048"},
    "4:3": {"sd": "768x576", "hd": "1024x768", "fhd": "1472x1140", "4k": "2048x1536"},
    "3:4": {"sd": "576x768", "hd": "768x1024", "fhd": "1140x1472", "4k": "1536x2048"},
    "21:9": {"sd": "1280x544", "hd": "1920x800", "fhd": "2560x1080", "4k": "3840x1632"},
}


def duration_to_frames(seconds: float, fps: float = 24.0) -> int:
    frames = max(1, int(round(float(seconds) * fps)))
    if frames % 2 == 0:
        frames += 1
    return frames


def resolution_for(
    project: Project,
    options: dict[str, Any] | None = None,
    *,
    quality: str | None = None,
) -> str:
    if options and options.get("resolution"):
        return str(options["resolution"])
    mapping = ASPECT_RESOLUTIONS.get(project.aspect_ratio, ASPECT_RESOLUTIONS["16:9"])
    chosen = quality or getattr(project, "generate_quality", None) or "hd"
    return mapping.get(chosen, mapping["hd"])


def export_resolution_for(project: Project) -> str:
    mapping = ASPECT_RESOLUTIONS.get(project.aspect_ratio, ASPECT_RESOLUTIONS["16:9"])
    chosen = getattr(project, "export_quality", None) or "hd"
    return mapping.get(chosen, mapping["hd"])


def catalog_defaults(catalog: Any, model_type: str) -> dict[str, Any]:
    if catalog is None:
        return {}
    entry = catalog.get(model_type)
    if entry is None:
        return {}
    data = copy.deepcopy(entry.raw)
    data.pop("model", None)
    return data


def asset_by_role(request: GenerationRequest, role: str) -> list[Path]:
    bound = getattr(request, "bound", None)
    if bound and bound.files:
        return [f.path for f in bound.files if f.role == role and f.path.exists()]
    if request.scene is None:
        return list(request.reference_paths)
    project = request.project
    paths: list[Path] = []
    for ref in request.scene.asset_refs:
        if ref.role != role:
            continue
        asset = project.get_asset(ref.asset_id)
        if asset is None:
            continue
        path = asset.absolute_path(project.dir())
        if path.exists():
            paths.append(path)
    return paths


def all_reference_images(request: GenerationRequest) -> list[Path]:
    bound = getattr(request, "bound", None)
    if bound and bound.images:
        return [f.path for f in bound.images if f.path.exists()]
    if request.reference_paths:
        return [p for p in request.reference_paths if p.exists()]
    roles = ("first_frame", "last_frame", "subject", "prop", "background", "style", "motion", "reference", "wardrobe", "pose")
    seen: set[str] = set()
    paths: list[Path] = []
    for role in roles:
        for path in asset_by_role(request, role):
            key = str(path)
            if key not in seen:
                seen.add(key)
                paths.append(path)
    return paths


def merge_options(project: Project, scene: Scene | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = dict(project.default_model_options or {})
    if scene and scene.model_options_override:
        merged.update(scene.model_options_override)
    if extra:
        merged.update(extra)
    return merged


def _apply_bound_attachments(settings: dict[str, Any], request: GenerationRequest) -> None:
    bound = getattr(request, "bound", None)
    if not bound or not bound.files:
        return
    contract = bound.contract
    first = [f.path for f in bound.files if f.role == "first_frame" and f.media == "image"]
    last = [f.path for f in bound.files if f.role == "last_frame" and f.media == "image"]
    extra_images = [
        f.path
        for f in bound.images
        if f.role not in {"first_frame", "last_frame"}
    ]
    if first:
        settings["image_start"] = [str(p) for p in first]
    elif extra_images and (
        contract.wan2gp_image_key == "image_start"
        or str(request.model_type).startswith(("i2v", "flf2v", "ti2v"))
    ):
        settings["image_start"] = [str(extra_images[0])]
        extra_images = extra_images[1:]
    if last:
        settings["image_end"] = [str(p) for p in last]
    if extra_images:
        settings[contract.wan2gp_image_key] = [str(p) for p in extra_images]
    videos = [f.path for f in bound.videos]
    if videos and contract.max_videos > 0:
        key = contract.wan2gp_video_key
        if key == "video_guide":
            settings["video_guide"] = str(videos[0])
            if len(videos) > 1:
                settings["video_guide2"] = str(videos[1])
        else:
            settings[key] = str(videos[0]) if len(videos) == 1 else [str(p) for p in videos]
    audios = [f.path for f in bound.audios]
    if audios and contract.max_audio > 0:
        settings[contract.wan2gp_audio_key] = str(audios[0])


def base_settings(request: GenerationRequest, prompt: str, *, fps: float = 24.0) -> dict[str, Any]:
    options = request.options or {}
    settings: dict[str, Any] = {
        "model_type": request.model_type,
        "prompt": prompt,
        "resolution": resolution_for(request.project, options),
        "seed": int(options.get("seed", -1)),
        "num_inference_steps": int(options.get("num_inference_steps", 8)),
    }
    if request.negative_prompt:
        settings["negative_prompt"] = request.negative_prompt
    if request.kind == "video" and request.scene is not None:
        settings["video_length"] = duration_to_frames(request.scene.duration_seconds, fps)
        settings["force_fps"] = fps
    if request.quantization:
        settings["transformer_quantization"] = request.quantization
    lora = options.get("activated_loras") or options.get("lora")
    if lora:
        settings["activated_loras"] = lora if isinstance(lora, list) else [lora]
        settings["loras_multipliers"] = str(options.get("loras_multipliers", "1.0"))
    if options.get("guidance_scale") is not None:
        settings["guidance_scale"] = float(options["guidance_scale"])
    bound = getattr(request, "bound", None)
    if bound and bound.files:
        _apply_bound_attachments(settings, request)
        return settings
    first = asset_by_role(request, "first_frame")
    last = asset_by_role(request, "last_frame")
    refs = all_reference_images(request)
    if first:
        settings["image_start"] = [str(p) for p in first]
    if last:
        settings["image_end"] = [str(p) for p in last]
    extra_refs = [p for p in refs if p not in first and p not in last]
    if extra_refs:
        settings["image_refs"] = [str(p) for p in extra_refs]
    audio = asset_by_role(request, "audio")
    if audio:
        settings["audio_guide"] = str(audio[0])
    return settings


def apply_catalog_defaults(settings: dict[str, Any], catalog: Any, model_type: str) -> dict[str, Any]:
    defaults = catalog_defaults(catalog, model_type)
    merged = {**defaults, **settings}
    merged["model_type"] = model_type
    return merged
