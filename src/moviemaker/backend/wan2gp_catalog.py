"""Scan Wan2GP defaults/*.json and finetunes/*.json into a live catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


IMAGE_ARCHITECTURE_HINTS = (
    "flux",
    "qwen_image",
    "hidream",
    "z_image",
    "krea2",
    "chroma",
    "pi_flux",
    "kiwi_edit",
)


@dataclass
class CatalogEntry:
    model_type: str
    architecture: str
    name: str
    description: str
    urls: list[str]
    image_outputs: bool
    source: str
    raw: dict[str, Any]
    default_steps: int | None = None
    default_resolution: str | None = None
    default_video_length: int | None = None
    quantizations: list[str] = field(default_factory=list)

    @property
    def kind(self) -> str:
        return "image" if self.image_outputs else "video"


def _quantizations_from_urls(urls: Iterable[str]) -> list[str]:
    found: list[str] = []
    for url in urls:
        name = url.lower()
        if "gguf_q4" in name or "q4_k" in name:
            found.append("gguf_q4")
        elif "gguf_q5" in name or "q5_k" in name:
            found.append("gguf_q5")
        elif "gguf_q6" in name or "q6_k" in name:
            found.append("gguf_q6")
        elif "gguf_q8" in name or "q8_0" in name:
            found.append("gguf_q8")
        elif "nvfp4" in name or "fp4" in name:
            found.append("fp4")
        elif "fp8" in name:
            found.append("fp8")
        elif "int8" in name or "quanto" in name:
            found.append("int8")
        elif "bf16" in name or "mbf16" in name:
            found.append("bf16")
        elif "fp16" in name or "mfp16" in name:
            found.append("fp16")
        elif "pruned" in name:
            found.append("pruned")
    ordered: list[str] = []
    for item in found:
        if item not in ordered:
            ordered.append(item)
    if not ordered:
        ordered = ["bf16"]
    return ordered


def _is_image(architecture: str, raw: dict[str, Any]) -> bool:
    model = raw.get("model") or {}
    if model.get("image_outputs") or raw.get("image_outputs"):
        return True
    arch = architecture.lower()
    return any(hint in arch for hint in IMAGE_ARCHITECTURE_HINTS)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _entry_from_file(path: Path, source: str) -> CatalogEntry | None:
    raw = _load_json(path)
    if not raw:
        return None
    model = raw.get("model") if isinstance(raw.get("model"), dict) else {}
    architecture = str(model.get("architecture") or path.stem)
    urls: list[str] = []
    for key in ("URLs", "URLs2"):
        value = model.get(key) or raw.get(key)
        if isinstance(value, str):
            urls.append(value)
        elif isinstance(value, list):
            urls.extend(str(u) for u in value)
    return CatalogEntry(
        model_type=path.stem,
        architecture=architecture,
        name=str(model.get("name") or path.stem),
        description=str(model.get("description") or ""),
        urls=urls,
        image_outputs=_is_image(architecture, raw),
        source=source,
        raw=raw,
        default_steps=raw.get("num_inference_steps"),
        default_resolution=raw.get("resolution"),
        default_video_length=raw.get("video_length"),
        quantizations=_quantizations_from_urls(urls),
    )


class Wan2GPCatalog:
    def __init__(self, wan2gp_path: Path | None) -> None:
        self.wan2gp_path = Path(wan2gp_path) if wan2gp_path else None
        self.entries: dict[str, CatalogEntry] = {}
        self.by_architecture: dict[str, list[CatalogEntry]] = {}
        if self.wan2gp_path:
            self.refresh()

    def refresh(self) -> None:
        self.entries.clear()
        self.by_architecture.clear()
        if not self.wan2gp_path or not self.wan2gp_path.is_dir():
            return
        for folder, source in (("defaults", "defaults"), ("finetunes", "finetunes")):
            root = self.wan2gp_path / folder
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.json")):
                entry = _entry_from_file(path, source)
                if entry is None:
                    continue
                self.entries[entry.model_type] = entry
                self.by_architecture.setdefault(entry.architecture, []).append(entry)

    def get(self, model_type: str) -> CatalogEntry | None:
        return self.entries.get(model_type)

    def list_entries(self, kind: str | None = None) -> list[CatalogEntry]:
        items = list(self.entries.values())
        if kind:
            items = [e for e in items if e.kind == kind]
        return sorted(items, key=lambda e: e.name.lower())

    def architectures(self, kind: str | None = None) -> list[str]:
        return sorted({e.architecture for e in self.list_entries(kind)})

    def loras(self, family: str | None = None) -> list[str]:
        if not self.wan2gp_path:
            return []
        roots = [self.wan2gp_path / "loras"]
        if family:
            roots.append(self.wan2gp_path / "loras" / family)
        found: list[str] = []
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() in {".safetensors", ".pt", ".ckpt"}:
                    found.append(str(path.relative_to(self.wan2gp_path)))
        return sorted(set(found))
