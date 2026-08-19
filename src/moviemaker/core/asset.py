"""Asset model, tree helpers, and filesystem helpers."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

AssetType = Literal["image", "video", "audio", "group"]
AssetSource = Literal["upload", "generated", "edited", "downloaded"]
MappedKind = Literal[
    "subject",
    "prop",
    "background",
    "style_ref",
    "motion_ref",
    "audio",
    "other",
]
VariantKind = Literal["default", "pose", "outfit", "expression", "angle", "still", "clip", "other"]

HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*$")


class Asset(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str
    handle: str = ""
    mapped_name: str = ""
    mapped_kind: MappedKind = "other"
    variant_kind: VariantKind = "default"
    is_default: bool = False
    type: AssetType = "image"
    source: AssetSource = "upload"
    path: str = ""
    parent_asset_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    def absolute_path(self, project_dir: Path) -> Path:
        p = Path(self.path)
        if p.is_absolute():
            return p
        return project_dir / p

    def has_file(self, project_dir: Path | None = None) -> bool:
        if not self.path:
            return False
        if project_dir is None:
            return True
        return self.absolute_path(project_dir).exists()

    @property
    def leaf_handle(self) -> str:
        return self.handle.rsplit("/", 1)[-1] if self.handle else ""

    @property
    def parent_handle(self) -> str:
        if "/" not in self.handle:
            return ""
        return self.handle.rsplit("/", 1)[0]


def slugify(name: str) -> str:
    text = (name or "").strip().lower().replace("\\", "/")
    text = text.split("/")[-1]
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "asset"


def unique_handle(existing: list[Asset], desired: str, parent: Asset | None = None) -> str:
    leaf = slugify(desired)
    prefix = ""
    if parent is not None:
        prefix = (parent.handle or slugify(parent.name)).rstrip("/")
        candidate = f"{prefix}/{leaf}"
    else:
        candidate = leaf
    used = {a.handle.lower() for a in existing if a.handle}
    if candidate.lower() not in used:
        return candidate
    index = 2
    while f"{candidate}-{index}".lower() in used:
        index += 1
    return f"{candidate}-{index}"


def next_mapped_name(existing: list[Asset], kind: MappedKind) -> str:
    prefix = {
        "subject": "subject",
        "prop": "prop",
        "background": "background",
        "style_ref": "style_ref",
        "motion_ref": "motion_ref",
        "audio": "audio",
        "other": "asset",
    }[kind]
    used = {a.mapped_name for a in existing}
    index = 1
    while f"{prefix}_{index}" in used:
        index += 1
    return f"{prefix}_{index}"


def copy_into_project(
    src: Path,
    project_dir: Path,
    *,
    name: str | None = None,
    subdir: str | None = None,
) -> Path:
    dest_dir = project_dir / "assets"
    if subdir:
        dest_dir = dest_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (name or src.name)
    if dest.exists():
        dest = dest_dir / f"{dest.stem}_{uuid.uuid4().hex[:6]}{dest.suffix}"
    shutil.copy2(src, dest)
    return dest


def asset_by_id(assets: list[Asset], asset_id: str) -> Asset | None:
    return next((a for a in assets if a.id == asset_id), None)


def asset_by_handle(assets: list[Asset], handle: str) -> Asset | None:
    key = normalize_handle(handle)
    if not key:
        return None
    for asset in assets:
        if (asset.handle or "").lower() == key:
            return asset
    slug = slugify(handle)
    for asset in assets:
        if not asset.parent_asset_id and slugify(asset.name) == slug:
            return asset
        if slugify(asset.name) == slug and (asset.handle or "").lower().endswith("/" + slug):
            return asset
    return None


def normalize_handle(handle: str) -> str:
    text = (handle or "").strip().lower().replace("\\", "/")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"/+", "/", text).strip("/")
    return text


def root_of(assets: list[Asset], asset: Asset) -> Asset:
    current = asset
    seen: set[str] = set()
    while current.parent_asset_id and current.parent_asset_id not in seen:
        seen.add(current.id)
        parent = asset_by_id(assets, current.parent_asset_id)
        if parent is None:
            break
        current = parent
    return current


def children_of(assets: list[Asset], parent_id: str) -> list[Asset]:
    return [a for a in assets if a.parent_asset_id == parent_id]


def roots(assets: list[Asset]) -> list[Asset]:
    return [a for a in assets if not a.parent_asset_id]


def walk_tree(assets: list[Asset]) -> list[tuple[Asset, int]]:
    by_parent: dict[str | None, list[Asset]] = {}
    for asset in assets:
        by_parent.setdefault(asset.parent_asset_id, []).append(asset)
    ordered: list[tuple[Asset, int]] = []

    def visit(parent_id: str | None, depth: int) -> None:
        for asset in by_parent.get(parent_id, []):
            ordered.append((asset, depth))
            visit(asset.id, depth + 1)

    visit(None, 0)
    return ordered


def default_file_asset(assets: list[Asset], asset: Asset) -> Asset | None:
    """File used when the parent (or this node) is tagged with @handle."""
    kids = children_of(assets, asset.id)
    if kids:
        marked = next((c for c in kids if c.is_default and c.path), None)
        if marked:
            return marked
        with_file = next((c for c in kids if c.path), None)
        if with_file:
            return with_file
    if asset.path:
        return asset
    return None


def set_default_child(assets: list[Asset], child: Asset) -> None:
    if not child.parent_asset_id:
        child.is_default = True
        return
    for sibling in children_of(assets, child.parent_asset_id):
        sibling.is_default = sibling.id == child.id
    child.is_default = True


def rename_handle(assets: list[Asset], asset: Asset, new_handle: str) -> str:
    parent = asset_by_id(assets, asset.parent_asset_id) if asset.parent_asset_id else None
    handle = unique_handle([a for a in assets if a.id != asset.id], new_handle, parent)
    old = asset.handle
    asset.handle = handle
    if old:
        prefix = old + "/"
        for child in assets:
            if child.handle.startswith(prefix):
                child.handle = handle + child.handle[len(old) :]
    return handle


def ensure_asset_handles(assets: list[Asset]) -> None:
    """Backfill handles on loaded projects that predate this field."""
    for asset, _depth in walk_tree(assets):
        if asset.handle and HANDLE_RE.match(asset.handle):
            continue
        parent = asset_by_id(assets, asset.parent_asset_id) if asset.parent_asset_id else None
        asset.handle = unique_handle([a for a in assets if a.id != asset.id and a.handle], asset.name, parent)
    roots_list = roots(assets)
    for root in roots_list:
        kids = children_of(assets, root.id)
        if kids and not any(c.is_default for c in kids):
            first = next((c for c in kids if c.path), kids[0])
            first.is_default = True
