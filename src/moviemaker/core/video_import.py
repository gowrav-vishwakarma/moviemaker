"""Download a timed clip from YouTube or any yt-dlp source into the project."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

MAX_CLIP_SECONDS = 15.0

_HMS = re.compile(
    r"^(?:(?P<h>\d+):)?(?P<m>\d{1,2}):(?P<s>\d{1,2}(?:\.\d+)?)$|^(?P<sec>\d+(?:\.\d+)?)s?$"
)


def parse_timestamp(value: str) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    match = _HMS.match(text)
    if not match:
        raise ValueError(f"Cannot parse timestamp: {value!r} (use 0:12 or 12.5)")
    if match.group("sec") is not None:
        return float(match.group("sec"))
    hours = float(match.group("h") or 0)
    minutes = float(match.group("m") or 0)
    seconds = float(match.group("s") or 0)
    return hours * 3600 + minutes * 60 + seconds


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:06.3f}".rstrip("0").rstrip(".")
    return f"{minutes}:{secs:06.3f}".rstrip("0").rstrip(".")


def download_clip(
    url: str,
    dest: Path,
    *,
    start: str,
    end: str,
    max_seconds: float = MAX_CLIP_SECONDS,
) -> Path:
    start_s = parse_timestamp(start)
    end_s = parse_timestamp(end)
    if end_s <= start_s:
        raise ValueError("End time must be after start time")
    if end_s - start_s > max_seconds + 0.05:
        raise ValueError(f"Clip is {end_s - start_s:.1f}s; max is {max_seconds:g}s for model video refs")
    yt = shutil.which("yt-dlp")
    if not yt:
        raise RuntimeError("yt-dlp is not installed or not on PATH")
    dest.parent.mkdir(parents=True, exist_ok=True)
    output = dest.with_suffix(".%(ext)s")
    section = f"*{format_timestamp(start_s)}-{format_timestamp(end_s)}"
    cmd = [
        yt,
        "--no-playlist",
        "--force-keyframes-at-cuts",
        "--download-sections",
        section,
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "-o",
        str(output),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "yt-dlp failed")[-2000:])
    found = list(dest.parent.glob(dest.stem + ".*"))
    videos = [p for p in found if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not videos:
        raise RuntimeError("yt-dlp finished but no video file was written")
    chosen = videos[0]
    if chosen.suffix.lower() != ".mp4":
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            mp4 = dest.with_suffix(".mp4")
            subprocess.run(
                [ffmpeg, "-y", "-i", str(chosen), "-c:v", "libx264", "-c:a", "aac", str(mp4)],
                capture_output=True,
                check=False,
            )
            if mp4.exists():
                chosen.unlink(missing_ok=True)
                return mp4
    return chosen
