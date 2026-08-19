"""Async generation job queue with cancel, retry, and logs."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from moviemaker.core.project import Project, save_project
from moviemaker.plugins.base import GenerationRequest, GenerationResult, JobStatus, ModelPlugin


@dataclass
class Job:
    id: str
    kind: str
    label: str
    scene_id: str | None
    plugin_id: str
    model_type: str
    quantization: str | None
    status: JobStatus = "pending"
    progress: float = 0.0
    log: str = ""
    error: str | None = None
    retries: int = 0
    max_retries: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    result: GenerationResult | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    request_factory: Callable[[], GenerationRequest] | None = None
    plugin: ModelPlugin | None = None
    extend_from: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class GenerationQueue:
    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self.jobs: list[Job] = []
        self.on_change = on_change
        self._lock = asyncio.Lock()
        self._worker: asyncio.Task[None] | None = None
        self._wakeup = asyncio.Event()
        self.concurrency = 1

    def _notify(self) -> None:
        if self.on_change:
            self.on_change()

    def enqueue(
        self,
        *,
        kind: str,
        label: str,
        plugin: ModelPlugin,
        request_factory: Callable[[], GenerationRequest],
        scene_id: str | None,
        model_type: str,
        quantization: str | None,
        extend_from: Path | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:8],
            kind=kind,
            label=label,
            scene_id=scene_id,
            plugin_id=plugin.id,
            model_type=model_type,
            quantization=quantization,
            request_factory=request_factory,
            plugin=plugin,
            extend_from=extend_from,
            extra=extra or {},
        )
        self.jobs.insert(0, job)
        self._notify()
        self._wakeup.set()
        return job

    def cancel(self, job_id: str) -> None:
        for job in self.jobs:
            if job.id == job_id and job.status in {"pending", "running"}:
                job.cancel_event.set()
                if job.status == "pending":
                    job.status = "cancelled"
                self._notify()

    def retry(self, job_id: str) -> None:
        for job in self.jobs:
            if job.id == job_id and job.status in {"failed", "cancelled"}:
                job.status = "pending"
                job.error = None
                job.cancel_event = asyncio.Event()
                job.retries += 1
                self._wakeup.set()
                self._notify()

    def pending(self) -> list[Job]:
        return [j for j in self.jobs if j.status == "pending"]

    def active(self) -> list[Job]:
        return [j for j in self.jobs if j.status in {"pending", "running"}]

    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        while True:
            self._wakeup.clear()
            pending_ordered = [j for j in reversed(self.jobs) if j.status == "pending"]
            if not pending_ordered:
                await self._wakeup.wait()
                continue
            await self._execute(pending_ordered[0])

    async def _execute(self, job: Job) -> None:
        if job.plugin is None or job.request_factory is None:
            job.status = "failed"
            job.error = "Job is missing plugin or request"
            self._notify()
            return
        job.status = "running"
        self._notify()
        request = job.request_factory()
        request.dry_run = bool(request.dry_run)
        request.cancel_event = job.cancel_event
        try:
            if job.extend_from:
                result = await job.plugin.extend(job.extend_from, request)
            else:
                result = await job.plugin.generate(request)
        except Exception as exc:  # noqa: BLE001 - surface any backend failure
            result = GenerationResult(status="failed", error=str(exc))
        if job.cancel_event.is_set():
            result.status = "cancelled"
            result.error = result.error or "Cancelled"
        job.result = result
        job.status = result.status
        job.error = result.error
        job.log = result.log_text
        job.progress = 100 if result.status == "completed" else job.progress
        if job.status == "failed" and job.retries < job.max_retries and not job.cancel_event.is_set():
            job.retries += 1
            job.status = "pending"
            job.cancel_event = asyncio.Event()
            self._wakeup.set()
        self._notify()


def write_job_log(project: Project, scene_id: str | None, text: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{scene_id or 'job'}_{stamp}.log"
    path = project.logs_dir() / name
    path.write_text(text, encoding="utf-8")
    return path


def apply_scene_result(project: Project, scene_id: str, result: GenerationResult) -> None:
    scene = project.get_scene(scene_id)
    if scene is None:
        return
    if result.status == "completed":
        scene.status = "done"
        if result.video_path:
            scene.output_path = str(result.video_path)
        if result.audio_path:
            scene.audio_output_path = str(result.audio_path)
        scene.error = None
        # attach generated audio to dialogue layer when present
        if result.audio_path:
            from moviemaker.core.timeline import Clip

            audio_layers = [l for l in project.layers if l.type == "audio"]
            if audio_layers:
                audio_layers[0].clips.append(
                    Clip(
                        scene_id=scene.id,
                        start_time_seconds=scene.start_time_seconds,
                        duration_seconds=scene.duration_seconds,
                        label=f"{scene.title} audio",
                    )
                )
                audio_layers[0].clips[-1].asset_id = None
                # store path in label metadata via scene.audio_output_path
    elif result.status == "cancelled":
        scene.status = "cancelled"
        scene.error = result.error
    else:
        scene.status = "failed"
        scene.error = result.error
    scene.generation_log = (result.log_text or "")[-4000:]
    save_project(project)
