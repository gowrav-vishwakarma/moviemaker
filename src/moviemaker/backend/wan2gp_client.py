"""Async Wan2GP subprocess client (`wgp.py --process`)."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from moviemaker.plugins.base import GenerationResult
from moviemaker.settings import AppSettings

ProgressCallback = Callable[[str, float | None], Awaitable[None] | None]


class BackendClient(Protocol):
    async def process(
        self,
        settings: dict[str, Any],
        output_dir: Path,
        *,
        dry_run: bool = False,
        log_path: Path | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> GenerationResult: ...


@dataclass
class ProcessRun:
    returncode: int
    stdout: str
    stderr: str
    cancelled: bool = False
    files: list[Path] = field(default_factory=list)


PROGRESS_RE = re.compile(r"(\d{1,3})\s*%")


class Wan2GPClient:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def _python(self) -> Path:
        py = self.settings.resolved_wan2gp_python()
        if py is None:
            raise RuntimeError("Wan2GP Python interpreter not found. Set the path in Settings.")
        return py

    def _root(self) -> Path:
        if not self.settings.wan2gp_path:
            raise RuntimeError("Wan2GP path is not configured.")
        return Path(self.settings.wan2gp_path)

    async def process(
        self,
        settings: dict[str, Any],
        output_dir: Path,
        *,
        dry_run: bool = False,
        log_path: Path | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> GenerationResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        settings_path = output_dir / "_wan2gp_settings.json"
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        cmd = [
            str(self._python()),
            "wgp.py",
            "--process",
            str(settings_path),
            "--output-dir",
            str(output_dir),
        ]
        if dry_run:
            cmd.append("--dry-run")
        before = set(output_dir.glob("*"))
        run = await _run_subprocess(
            cmd,
            cwd=self._root(),
            log_path=log_path,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )
        after = [p for p in output_dir.glob("*") if p not in before and p.name != "_wan2gp_settings.json"]
        videos = [p for p in after if p.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}]
        audios = [p for p in after if p.suffix.lower() in {".wav", ".mp3", ".flac", ".aac"}]
        images = [p for p in after if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
        if run.cancelled:
            return GenerationResult(status="cancelled", error="Cancelled", log_text=run.stdout)
        if run.returncode != 0:
            return GenerationResult(
                status="failed",
                error=(run.stderr or run.stdout or f"Wan2GP exited with {run.returncode}")[-2000:],
                log_text=run.stdout + "\n" + run.stderr,
            )
        if dry_run:
            return GenerationResult(
                status="completed",
                metadata={"dry_run": True, "stdout": run.stdout[-4000:]},
                log_text=run.stdout,
            )
        return GenerationResult(
            status="completed",
            video_path=videos[0] if videos else None,
            audio_path=audios[0] if audios else None,
            image_path=images[0] if images else None,
            metadata={"files": [str(p) for p in after]},
            log_text=run.stdout,
        )


async def _run_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path | None,
    on_progress: ProgressCallback | None,
    cancel_event: asyncio.Event | None,
) -> ProcessRun:
    log_handle = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("w", encoding="utf-8")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    chunks: list[str] = []

    async def _pump() -> None:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            chunks.append(text)
            if log_handle:
                log_handle.write(text)
                log_handle.flush()
            if on_progress:
                percent = None
                match = PROGRESS_RE.search(text)
                if match:
                    percent = float(match.group(1))
                result = on_progress(text.rstrip(), percent)
                if asyncio.iscoroutine(result):
                    await result

    pump_task = asyncio.create_task(_pump())
    cancelled = False
    try:
        while True:
            if cancel_event and cancel_event.is_set():
                cancelled = True
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=8)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                break
            if proc.returncode is not None:
                break
            await asyncio.sleep(0.2)
        await pump_task
    finally:
        if log_handle:
            log_handle.close()
    stdout = "".join(chunks)
    return ProcessRun(
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout,
        stderr="",
        cancelled=cancelled,
    )
