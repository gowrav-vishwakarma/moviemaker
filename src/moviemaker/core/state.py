"""In-memory application state shared by every UI panel."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from moviemaker.backend.mock_client import MockClient
from moviemaker.backend.wan2gp_catalog import Wan2GPCatalog
from moviemaker.backend.wan2gp_client import Wan2GPClient
from moviemaker.core.asset import (
    Asset,
    copy_into_project,
    next_mapped_name,
    unique_handle,
)
from moviemaker.core.hardware import HardwareProfile
from moviemaker.core.project import Project, create_project, load_project, save_project
from moviemaker.core.scene import Scene
from moviemaker.core.zipio import export_zip, import_zip
from moviemaker.generation.batch_runner import enqueue_scenes
from moviemaker.generation.queue import GenerationQueue, apply_scene_result
from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.registry import PluginRegistry, build_registry
from moviemaker.plugins.settings_common import merge_options
from moviemaker.settings import AppSettings, load_settings, save_settings, apply_auto_detect, looks_like_wan2gp, wan2gp_python


Listener = Callable[[], None]


class AppState:
    def __init__(self) -> None:
        self.settings: AppSettings = load_settings()
        self.catalog = Wan2GPCatalog(self.settings.wan2gp_path)
        self.registry: PluginRegistry = build_registry()
        self.client: Any = self._make_client()
        self.registry.bind(self.catalog, self.client)
        self.project: Project | None = None
        self.selected_scene_id: str | None = None
        self.selected_asset_id: str | None = None
        self.editing_scene: bool = False
        self.status_message: str = "Ready"
        self.play_source: str | None = None
        self.play_mode: str = "scene"
        self.last_export: Path | None = None
        self.queue = GenerationQueue(on_change=self._on_queue_change)
        self._listeners: list[Listener] = []
        self._seen_job_results: set[str] = set()
        self.installed_upscalers: list[str] = []
        self._refresh_upscalers()

    def _make_client(self) -> Any:
        if self.settings.use_mock_backend or not self.settings.wan2gp_ready():
            return MockClient()
        return Wan2GPClient(self.settings)

    def reload_backend(self) -> None:
        apply_auto_detect(self.settings)
        self.catalog = Wan2GPCatalog(self.settings.wan2gp_path)
        self.client = self._make_client()
        self.registry.bind(self.catalog, self.client)
        self._refresh_upscalers()
        self.emit()

    def _refresh_upscalers(self) -> None:
        from moviemaker.export.upscale import probe_installed_upscalers

        self.installed_upscalers = probe_installed_upscalers(self.settings.wan2gp_path)

    def subscribe(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def emit(self) -> None:
        for fn in list(self._listeners):
            fn()

    def set_status(self, message: str) -> None:
        self.status_message = message
        self.emit()

    def persist_settings(self) -> None:
        if self.settings.wan2gp_path and looks_like_wan2gp(Path(self.settings.wan2gp_path)):
            self.settings.wan2gp_python = wan2gp_python(Path(self.settings.wan2gp_path))
        save_settings(self.settings)
        self.reload_backend()

    def persist_project(self) -> None:
        if self.project:
            save_project(self.project)

    @property
    def selected_scene(self) -> Scene | None:
        if not self.project or not self.selected_scene_id:
            return None
        return self.project.get_scene(self.selected_scene_id)

    @property
    def selected_asset(self) -> Asset | None:
        if not self.project or not self.selected_asset_id:
            return None
        return self.project.get_asset(self.selected_asset_id)

    @property
    def hardware(self) -> HardwareProfile:
        return self.settings.hardware_profile

    def open_project(self, folder: Path) -> None:
        self.project = load_project(folder)
        self.selected_scene_id = self.project.scenes[0].id if self.project.scenes else None
        self.set_status(f"Opened {self.project.name}")

    def new_project(self, folder: Path, name: str, **kwargs: Any) -> None:
        if "default_model_id" not in kwargs:
            kwargs["default_model_id"] = "minimax_h3"
        self.project = create_project(folder, name, hardware=self.hardware, **kwargs)
        if self.catalog.get("minimax_h3_fl2va"):
            self.project.default_model_type = "minimax_h3_fl2va"
            self.persist_project()
        self.selected_scene_id = None
        self.set_status(f"Created {self.project.name}")

    def select_scene(self, scene_id: str | None) -> None:
        self.selected_scene_id = scene_id
        scene = self.selected_scene
        if scene and scene.output_path:
            self.play_source = scene.output_path
            self.play_mode = "scene"
        self.emit()

    def open_scene_editor(self, scene_id: str | None) -> None:
        self.selected_scene_id = scene_id
        self.editing_scene = scene_id is not None
        scene = self.selected_scene
        if scene and scene.output_path:
            self.play_source = scene.output_path
            self.play_mode = "scene"
        self.emit()

    def close_scene_editor(self) -> None:
        self.editing_scene = False
        self.emit()

    def add_scene(self, title: str = "New scene", duration: float = 5.0) -> Scene:
        if not self.project:
            raise RuntimeError("No project open")
        start = self.project.total_duration()
        scene = Scene(
            title=title,
            duration_seconds=duration,
            start_time_seconds=start,
            model_id=self.project.default_model_id,
            model_type_override=self.project.default_model_type,
        )
        self.project.scenes.append(scene)
        self.project.sync_timeline()
        self.selected_scene_id = scene.id
        self.persist_project()
        self.emit()
        return scene

    def delete_scene(self, scene_id: str) -> None:
        if not self.project:
            return
        self.project.scenes = [s for s in self.project.scenes if s.id != scene_id]
        self.project.sync_timeline()
        if self.selected_scene_id == scene_id:
            self.selected_scene_id = self.project.scenes[0].id if self.project.scenes else None
        self.persist_project()
        self.emit()

    def move_scene(self, scene_id: str, delta: int) -> None:
        if not self.project:
            return
        scenes = self.project.scenes
        index = next((i for i, s in enumerate(scenes) if s.id == scene_id), None)
        if index is None:
            return
        new_index = max(0, min(len(scenes) - 1, index + delta))
        if new_index == index:
            return
        scenes.insert(new_index, scenes.pop(index))
        self.project.sync_timeline()
        self.persist_project()
        self.emit()

    def add_uploaded_asset(
        self,
        src: Path,
        name: str,
        mapped_kind: str = "subject",
        *,
        parent_id: str | None = None,
        variant_kind: str = "default",
        source: str = "upload",
    ) -> Asset:
        if not self.project:
            raise RuntimeError("No project open")
        parent = self.project.get_asset(parent_id) if parent_id else None
        subdir = parent.handle.replace("/", "_") if parent and parent.handle else None
        dest = copy_into_project(src, self.project.dir(), name=src.name, subdir=subdir)
        suffix = dest.suffix.lower()
        atype = "image"
        if suffix in {".mp4", ".mov", ".webm", ".mkv"}:
            atype = "video"
        elif suffix in {".wav", ".mp3", ".flac", ".aac", ".m4a"}:
            atype = "audio"
        if atype == "video" and mapped_kind == "subject":
            mapped_kind = "motion_ref"
        elif atype == "audio" and mapped_kind == "subject":
            mapped_kind = "audio"
        asset = Asset(
            name=name or dest.stem,
            handle=unique_handle(self.project.assets, name or dest.stem, parent),
            mapped_name=next_mapped_name(self.project.assets, mapped_kind),  # type: ignore[arg-type]
            mapped_kind=mapped_kind,  # type: ignore[arg-type]
            variant_kind=variant_kind,  # type: ignore[arg-type]
            type=atype,  # type: ignore[arg-type]
            source=source,  # type: ignore[arg-type]
            path=str(dest.relative_to(self.project.dir())),
            parent_asset_id=parent.id if parent else None,
            is_default=bool(parent and not any(a.parent_asset_id == parent.id and a.is_default for a in self.project.assets)),
        )
        self.project.assets.append(asset)
        self.selected_asset_id = asset.id
        self.persist_project()
        self.emit()
        return asset

    def import_url_clip(
        self,
        url: str,
        name: str,
        start: str,
        end: str,
        *,
        parent_id: str | None = None,
        mapped_kind: str = "motion_ref",
    ) -> Asset:
        if not self.project:
            raise RuntimeError("No project open")
        from moviemaker.core.video_import import download_clip

        parent = self.project.get_asset(parent_id) if parent_id else None
        slug = name or "clip"
        dest = self.project.tmp_dir() / f"{slug}.mp4"
        downloaded = download_clip(url, dest, start=start, end=end)
        asset = self.add_uploaded_asset(
            downloaded,
            name or downloaded.stem,
            mapped_kind,
            parent_id=parent.id if parent else None,
            variant_kind="clip",
            source="downloaded",
        )
        asset.metadata = {
            "url": url,
            "start": start,
            "end": end,
        }
        downloaded.unlink(missing_ok=True)
        self.persist_project()
        return asset

    def generate_scenes(self, scenes: list[Scene] | None = None, *, dry_run: bool = False, extend: bool = False) -> int:
        if not self.project:
            raise RuntimeError("No project open")
        targets = scenes or list(self.project.scenes)
        if not targets:
            raise RuntimeError("No scenes to generate")
        self.queue.start()
        count = enqueue_scenes(
            targets,
            project=self.project,
            registry=self.registry,
            queue=self.queue,
            settings=self.settings,
            dry_run=dry_run,
            extend=extend,
        )
        self.persist_project()
        self.set_status(f"Queued {count} scene(s)")
        return count

    def generate_selected(self, *, dry_run: bool = False, extend: bool = False) -> None:
        scene = self.selected_scene
        if scene is None:
            raise RuntimeError("Select a scene first")
        self.generate_scenes([scene], dry_run=dry_run, extend=extend)

    def generate_same_model_batch(self) -> None:
        scene = self.selected_scene
        if not self.project or scene is None:
            raise RuntimeError("Select a scene first")
        matches = [
            s
            for s in self.project.scenes
            if s.model_id == scene.model_id
            and (s.model_type_override or "") == (scene.model_type_override or "")
            and s.status != "done"
        ]
        self.generate_scenes(matches or [scene])

    def preview_prompt(self) -> str:
        scene = self.selected_scene
        if not self.project or scene is None:
            return ""
        plugin = self.registry.get(scene.model_id)
        hardware = self.hardware
        tier = plugin.select_tier(hardware)
        request = GenerationRequest(
            project=self.project,
            scene=scene,
            assets=list(self.project.assets),
            output_dir=self.project.clips_dir(),
            hardware_profile=hardware,
            options=merge_options(self.project, scene),
            model_type=scene.model_type_override or self.project.default_model_type or tier.model_type,
            quantization=scene.quantization_override or tier.quantization,
            prompt=scene.prompt,
            negative_prompt=scene.negative_prompt,
        )
        text = plugin.build_prompt(request)
        bound = request.bound
        if bound and bound.unmatched:
            tags = ", ".join(f"@{t}" for t in bound.unmatched)
            text = f"Unknown tags: {tags}\n\n{text}"
        if bound and bound.warnings:
            text = text + "\n\n" + "\n".join(bound.warnings)
        return text

    async def export_movie(self, crossfade: float = 0.25) -> Path:
        if not self.project:
            raise RuntimeError("No project open")
        from moviemaker.export.ffmpeg import export_project
        from moviemaker.export.upscale import pick_upscale_method, upscale_project_clips

        if self.project.upscale_enabled:
            plugin = self.registry.get(self.project.default_model_id)
            method = pick_upscale_method(
                self.project,
                self.installed_upscalers,
                plugin.capabilities.reference,
            )
            self.project.upscale_method = method
            self.set_status(f"Upscaling clips with {method}…")
            await upscale_project_clips(self.client, self.project, method)
        path = export_project(self.project, crossfade_seconds=crossfade, include_audio=True)
        self.last_export = path
        self.play_source = str(path)
        self.play_mode = "full"
        self.set_status(f"Exported {path.name}")
        return path

    def export_project_zip(self) -> Path:
        if not self.project:
            raise RuntimeError("No project open")
        path = export_zip(self.project)
        self.set_status(f"Wrote {path.name}")
        return path

    def import_project_zip(self, archive: Path, dest: Path) -> None:
        self.project = import_zip(archive, dest)
        self.selected_scene_id = self.project.scenes[0].id if self.project.scenes else None
        self.set_status(f"Imported {self.project.name}")

    def _on_queue_change(self) -> None:
        if self.project:
            for job in self.queue.jobs:
                token = f"{job.id}:{job.status}"
                if token in self._seen_job_results:
                    continue
                if job.status in {"completed", "failed", "cancelled"} and job.result:
                    self._seen_job_results.add(token)
                    if job.scene_id:
                        apply_scene_result(self.project, job.scene_id, job.result)
                        scene = self.project.get_scene(job.scene_id)
                        if scene and scene.output_path:
                            self.play_source = scene.output_path
                            self.play_mode = "scene"
                    if job.kind == "image" and job.status == "completed" and job.result.image_path:
                        self._attach_generated_image(job)
        self.emit()

    def _attach_generated_image(self, job) -> None:
        if not self.project or not job.result or not job.result.image_path:
            return
        from moviemaker.core.asset import Asset, next_mapped_name, unique_handle
        from moviemaker.core.project import save_project

        image_path = Path(job.result.image_path)
        try:
            rel = str(image_path.relative_to(self.project.dir()))
        except ValueError:
            rel = str(image_path)
        kind = job.extra.get("mapped_kind") or "subject"
        asset = Asset(
            name=job.extra.get("asset_name") or job.label,
            handle=unique_handle(self.project.assets, job.extra.get("asset_name") or job.label),
            mapped_name=next_mapped_name(self.project.assets, kind),
            mapped_kind=kind,
            type="image",
            source="edited" if job.extra.get("parent_asset_id") else "generated",
            path=rel,
            parent_asset_id=job.extra.get("parent_asset_id"),
            metadata={
                "plugin": job.extra.get("plugin_id") or job.plugin_id,
                "model_type": job.model_type,
                "prompt": job.extra.get("prompt") or "",
            },
        )
        self.project.assets.append(asset)
        self.selected_asset_id = asset.id
        save_project(self.project)
        self.play_source = str(image_path)
        self.play_mode = "asset"


STATE = AppState()
