"""Non-AI image operations used by Asset Studio."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PIL import Image

OpName = Literal["rotate_90", "rotate_180", "rotate_270", "flip_h", "flip_v", "resize"]


def apply_op(src: Path, dest: Path, op: OpName, *, size: tuple[int, int] | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img = img.convert("RGB")
        if op == "rotate_90":
            img = img.rotate(-90, expand=True)
        elif op == "rotate_180":
            img = img.rotate(180, expand=True)
        elif op == "rotate_270":
            img = img.rotate(90, expand=True)
        elif op == "flip_h":
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif op == "flip_v":
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif op == "resize" and size:
            img = img.resize(size, Image.Resampling.LANCZOS)
        img.save(dest)
    return dest


def crop_box(src: Path, dest: Path, box: tuple[int, int, int, int]) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        img.convert("RGB").crop(box).save(dest)
    return dest
