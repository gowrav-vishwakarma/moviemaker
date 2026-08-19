"""Mock generation backend used when Wan2GP is unavailable or for UI testing."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from moviemaker.backend.wan2gp_client import ProgressCallback
from moviemaker.plugins.base import GenerationResult


class MockClient:
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
        prompt = str(settings.get("prompt") or "mock")
        resolution = str(settings.get("resolution") or "1280x720")
        model_type = str(settings.get("model_type") or "mock")
        frames = int(settings.get("video_length") or 25)
        fps = float(settings.get("force_fps") or 24)
        duration = max(1.0, frames / max(fps, 1.0))
        log_lines = [
            f"[mock] model={model_type}",
            f"[mock] resolution={resolution} duration={duration:.1f}s",
            f"[mock] prompt={prompt[:180]}",
        ]
        if dry_run:
            text = "\n".join(log_lines + ["[mock] dry-run OK"])
            _write_log(log_path, text)
            return GenerationResult(status="completed", metadata={"dry_run": True, "mock": True}, log_text=text)
        if settings.get("mode") == "edit_postprocessing":
            source = Path(str(settings.get("video_source") or ""))
            if not source.exists():
                return GenerationResult(status="failed", error="Missing video_source for postprocessing")
            method = str(settings.get("spatial_upsampling") or "lanczos2")
            out = output_dir / f"{source.stem}_up_{method}.mp4"
            scale = 2
            if method.endswith("4"):
                scale = 4
            _scale_video(source, out, scale)
            text = "\n".join(log_lines + [f"[mock] upscale {method} -> {out.name}"])
            _write_log(log_path, text)
            return GenerationResult(status="completed", video_path=out, metadata={"mock": True, "upscale": method}, log_text=text)
        for step in range(1, 5):
            if cancel_event and cancel_event.is_set():
                return GenerationResult(status="cancelled", error="Cancelled", log_text="\n".join(log_lines))
            if on_progress:
                result = on_progress(f"[mock] step {step}/4", step * 25)
                if asyncio.iscoroutine(result):
                    await result
            await asyncio.sleep(0.15)
        width, height = _parse_res(resolution)
        stamp = datetime.now().strftime("%H%M%S")
        image_path = output_dir / f"mock_{stamp}.png"
        _render_card(image_path, width, height, model_type, prompt)
        video_path = None
        audio_path = None
        if settings.get("video_length"):
            video_path = output_dir / f"mock_{stamp}.mp4"
            audio_path = output_dir / f"mock_{stamp}.wav"
            _make_video(image_path, video_path, duration, fps)
            _make_tone(audio_path, duration)
        text = "\n".join(log_lines + ["[mock] completed"])
        _write_log(log_path, text)
        return GenerationResult(
            status="completed",
            video_path=video_path,
            audio_path=audio_path if audio_path and audio_path.exists() else None,
            image_path=image_path,
            metadata={"mock": True},
            log_text=text,
        )


def _write_log(path: Path | None, text: str) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _parse_res(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x")
        return max(64, int(w)), max(64, int(h))
    except ValueError:
        return 1280, 720


def _render_card(path: Path, width: int, height: int, title: str, prompt: str) -> None:
    img = Image.new("RGB", (width, height), (18, 18, 28))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width, 8], fill=(232, 165, 75))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 28)
        small = ImageFont.truetype("DejaVuSans.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((40, 48), "Movie Maker · mock output", fill=(232, 165, 75), font=small)
    draw.text((40, 90), title[:48], fill=(245, 245, 245), font=font)
    wrapped = prompt.replace("\n", " ")[:280]
    draw.text((40, 150), wrapped, fill=(180, 180, 196), font=small)
    img.save(path)


def _make_video(image_path: Path, video_path: Path, duration: float, fps: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        shutil.copy2(image_path, video_path.with_suffix(".png"))
        return
    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v",
        "libx264",
        "-t",
        f"{duration:.2f}",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(int(fps)),
        "-shortest",
        str(video_path),
    ]
    subprocess.run(cmd, capture_output=True, check=False)


def _make_tone(path: Path, duration: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration:.2f}",
            str(path),
        ],
        capture_output=True,
        check=False,
    )


def _scale_video(source: Path, dest: Path, scale: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        shutil.copy2(source, dest)
        return
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vf",
            f"scale=iw*{scale}:ih*{scale}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        capture_output=True,
        check=False,
    )
    if not dest.exists():
        shutil.copy2(source, dest)
