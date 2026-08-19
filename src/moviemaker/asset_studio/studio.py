"""Asset Studio: host image-kind plugins for generate/edit + PIL ops + lineage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from moviemaker.asset_studio.pil_ops import OpName, apply_op
from moviemaker.core.asset import Asset, next_mapped_name, unique_handle
from moviemaker.core.project import Project, save_project
from moviemaker.generation.queue import GenerationQueue
from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.registry import PluginRegistry
from moviemaker.plugins.settings_common import merge_options
from moviemaker.settings import AppSettings


def enqueue_image_job(
    *,
    project: Project,
    registry: PluginRegistry,
    queue: GenerationQueue,
    settings: AppSettings,
    plugin_id: str,
    model_type: str,
    prompt: str,
    options: dict[str, Any],
    reference_paths: list[Path],
    name: str,
    mapped_kind: str = "subject",
    parent_asset_id: str | None = None,
    dry_run: bool = False,
    on_complete: Callable[[Asset], None] | None = None,
) -> None:
    plugin = registry.get(plugin_id)
    hardware = settings.hardware_profile
    tier = plugin.select_tier(hardware)
    quantization = options.get("quantization") or tier.quantization
    output_dir = project.assets_dir()

    def factory() -> GenerationRequest:
        return GenerationRequest(
            project=project,
            scene=None,
            assets=list(project.assets),
            output_dir=output_dir,
            hardware_profile=hardware,
            options={**merge_options(project, None), **options},
            model_type=model_type or tier.model_type,
            quantization=quantization,
            prompt=prompt,
            reference_paths=reference_paths,
            kind="image",
            dry_run=dry_run or settings.dry_run_by_default,
            log_path=project.logs_dir() / "asset_studio.log",
        )

    job = queue.enqueue(
        kind="image",
        label=name,
        plugin=plugin,
        request_factory=factory,
        scene_id=None,
        model_type=model_type or tier.model_type,
        quantization=quantization,
        extra={
            "asset_name": name,
            "mapped_kind": mapped_kind,
            "parent_asset_id": parent_asset_id,
            "plugin_id": plugin_id,
            "prompt": prompt,
        },
    )
    return job


def pil_edit(project: Project, asset: Asset, op: OpName, *, size: tuple[int, int] | None = None) -> Asset:
    src = asset.absolute_path(project.dir())
    dest = project.assets_dir() / f"{src.stem}_{op}{src.suffix or '.png'}"
    apply_op(src, dest, op, size=size)
    child = Asset(
        name=f"{asset.name} ({op})",
        handle=unique_handle(project.assets, f"{asset.name}-{op}", asset if not asset.parent_asset_id else None),
        mapped_name=next_mapped_name(project.assets, asset.mapped_kind),
        mapped_kind=asset.mapped_kind,
        variant_kind="still",
        type="image",
        source="edited",
        path=str(dest.relative_to(project.dir())),
        parent_asset_id=asset.id if not asset.parent_asset_id else asset.parent_asset_id,
        metadata={"op": op, "parent": asset.id},
    )
    project.assets.append(child)
    save_project(project)
    return child
