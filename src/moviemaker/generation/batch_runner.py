"""Group pending scene jobs by architecture + model_type + quantization."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from moviemaker.core.hardware import HardwareProfile
from moviemaker.core.project import Project
from moviemaker.core.scene import Scene
from moviemaker.generation.queue import GenerationQueue
from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.registry import PluginRegistry
from moviemaker.plugins.settings_common import merge_options
from moviemaker.settings import AppSettings


def batch_key(architecture: str, model_type: str, quantization: str | None) -> tuple[str, str, str]:
    return (architecture, model_type, quantization or "")


def resolve_scene_backend(
    scene: Scene,
    project: Project,
    registry: PluginRegistry,
    hardware: HardwareProfile,
) -> tuple[str, str, str | None]:
    plugin = registry.get(scene.model_id)
    tier = plugin.select_tier(hardware)
    model_type = scene.model_type_override or project.default_model_type or tier.model_type or scene.model_id
    quantization = scene.quantization_override or tier.quantization
    architecture = plugin.capabilities.architectures[0] if plugin.capabilities.architectures else plugin.id
    if registry.architecture_map:
        for arch, plugin_id in registry.architecture_map.items():
            if plugin_id == plugin.id and (not scene.model_type_override or arch in (scene.model_type_override or "")):
                architecture = arch
                break
    return architecture, model_type, quantization


def group_scenes(
    scenes: Iterable[Scene],
    project: Project,
    registry: PluginRegistry,
    hardware: HardwareProfile,
) -> dict[tuple[str, str, str], list[Scene]]:
    grouped: dict[tuple[str, str, str], list[Scene]] = defaultdict(list)
    for scene in scenes:
        architecture, model_type, quantization = resolve_scene_backend(scene, project, registry, hardware)
        grouped[batch_key(architecture, model_type, quantization)].append(scene)
    return grouped


def enqueue_scenes(
    scenes: list[Scene],
    *,
    project: Project,
    registry: PluginRegistry,
    queue: GenerationQueue,
    settings: AppSettings,
    dry_run: bool = False,
    extend: bool = False,
) -> int:
    hardware = settings.hardware_profile
    groups = group_scenes(scenes, project, registry, hardware)
    count = 0
    # stable order: group then original scene order
    for (_arch, model_type, quantization), group in groups.items():
        plugin = registry.get(group[0].model_id)
        for scene in group:
            scene.status = "queued"
            scene_id = scene.id

            def factory(
                s: Scene = scene,
                mt: str = model_type,
                q: str | None = quantization or None,
            ) -> GenerationRequest:
                options = merge_options(project, s)
                log_path = project.logs_dir() / f"{s.id}.log"
                return GenerationRequest(
                    project=project,
                    scene=s,
                    assets=list(project.assets),
                    output_dir=project.clips_dir(),
                    hardware_profile=hardware,
                    options=options,
                    model_type=s.model_type_override or mt,
                    quantization=s.quantization_override or q,
                    prompt=s.prompt,
                    negative_prompt=s.negative_prompt,
                    kind="video",
                    dry_run=dry_run or settings.dry_run_by_default,
                    log_path=log_path,
                )

            existing = None
            if extend and scene.output_path:
                from pathlib import Path

                existing = Path(scene.output_path)
            queue.enqueue(
                kind="video",
                label=scene.title,
                plugin=plugin,
                request_factory=factory,
                scene_id=scene_id,
                model_type=scene.model_type_override or model_type,
                quantization=scene.quantization_override or quantization,
                extend_from=existing,
            )
            count += 1
    return count
