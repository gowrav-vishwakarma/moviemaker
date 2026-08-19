"""Parse @asset handles and rewrite them into model-native reference labels."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from moviemaker.core.asset import (
    Asset,
    asset_by_handle,
    asset_by_id,
    children_of,
    default_file_asset,
    normalize_handle,
    root_of,
    slugify,
)
from moviemaker.core.project import Project
from moviemaker.core.scene import Scene
from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import ReferenceContract

TAG_RE = re.compile(
    r"@\[([^\]]+)\]|@([A-Za-z0-9][A-Za-z0-9_-]*(?:/[A-Za-z0-9][A-Za-z0-9_-]*)*)"
)

SUBJECT_KINDS = {"subject", "prop", "background", "style_ref"}
MediaKind = Literal["image", "video", "audio"]
LabelKind = Literal["subject", "picture", "video", "audio", "name"]


@dataclass
class BoundFile:
    asset: Asset
    root: Asset
    path: Path
    media: MediaKind
    role: str
    label_kind: LabelKind
    index: int = 0
    slot: int = 0
    tag: str = ""
    label: str = ""


@dataclass
class BindResult:
    rewritten: str
    files: list[BoundFile] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    contract: ReferenceContract = field(default_factory=ReferenceContract)
    tag_labels: dict[str, str] = field(default_factory=dict)

    @property
    def images(self) -> list[BoundFile]:
        return [f for f in self.files if f.media == "image"]

    @property
    def videos(self) -> list[BoundFile]:
        return [f for f in self.files if f.media == "video"]

    @property
    def audios(self) -> list[BoundFile]:
        return [f for f in self.files if f.media == "audio"]

    def has_identity_refs(self) -> bool:
        return any(f.role not in {"first_frame", "last_frame"} for f in self.files)

    def label_for(self, handle: str) -> str:
        return self.tag_labels.get(normalize_handle(handle), "")


def parse_tags(text: str) -> list[tuple[str, str]]:
    """Return (raw_token, handle) in appearance order."""
    found: list[tuple[str, str]] = []
    for match in TAG_RE.finditer(text or ""):
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        raw = match.group(0)
        handle = normalize_handle(inner or "")
        if handle:
            found.append((raw, handle))
    return found


def mention_choices(assets: list[Asset]) -> list[tuple[str, str]]:
    """(handle, display) for autocomplete."""
    rows: list[tuple[str, str]] = []
    for asset in assets:
        if not asset.handle:
            continue
        label = f"@{asset.handle}  {asset.name}"
        if asset.variant_kind and asset.variant_kind != "default":
            label += f" · {asset.variant_kind}"
        rows.append((asset.handle, label))
    return rows


def infer_role(asset: Asset, scene_role: str | None = None) -> str:
    if scene_role in {"first_frame", "last_frame", "camera", "pose", "edit_source", "wardrobe", "motion"}:
        return scene_role
    if asset.type == "video":
        if asset.mapped_kind == "motion_ref":
            return "motion"
        return "camera"
    if asset.type == "audio" or asset.mapped_kind == "audio":
        return "voice"
    if asset.variant_kind == "outfit":
        return "wardrobe"
    if asset.variant_kind == "pose":
        return "pose"
    if asset.mapped_kind == "background":
        return "background"
    if asset.mapped_kind == "style_ref":
        return "style"
    if scene_role == "style":
        return "style"
    if scene_role == "audio":
        return "voice"
    return "identity"


def _media_of(asset: Asset) -> MediaKind | None:
    if asset.type == "video":
        return "video"
    if asset.type == "audio":
        return "audio"
    if asset.type == "image":
        return "image"
    return None


def _label_kind_for(contract: ReferenceContract, asset: Asset, role: str, is_root_tag: bool) -> LabelKind:
    if contract.uses_display_names:
        return "name"
    media = _media_of(asset)
    if media == "video":
        return "video" if contract.video_label else "name"
    if media == "audio":
        return "audio" if contract.audio_label else "name"
    if role in {"first_frame", "last_frame"}:
        return "picture" if contract.picture_label else "name"
    if contract.uses_subject_labels and asset.mapped_kind in SUBJECT_KINDS and is_root_tag:
        return "subject"
    if contract.uses_subject_labels and not is_root_tag and contract.picture_label:
        return "picture"
    if contract.picture_label:
        return "picture"
    return "name"


def _resolve_handle(assets: list[Asset], handle: str) -> Asset | None:
    direct = asset_by_handle(assets, handle)
    if direct:
        return direct
    if "/" in handle:
        parent_key, _, child_key = handle.partition("/")
        parent = asset_by_handle(assets, parent_key)
        if parent is None:
            return None
        for child in children_of(assets, parent.id):
            if child.leaf_handle == child_key or slugify(child.name) == child_key:
                return child
    return None


def _file_for_tag(assets: list[Asset], tagged: Asset, project_dir: Path) -> Asset | None:
    if tagged.parent_asset_id:
        return tagged if tagged.path else None
    if tagged.path:
        return tagged
    chosen = default_file_asset(assets, tagged)
    if chosen and chosen.path:
        return chosen
    return None


def bind_assets(
    *,
    text: str,
    project: Project,
    scene: Scene | None,
    contract: ReferenceContract,
    extra_paths: list[Path] | None = None,
) -> BindResult:
    assets = list(project.assets)
    project_dir = project.dir()
    unmatched: list[str] = []
    warnings: list[str] = []
    pending: list[tuple[str, Asset, Asset, str, bool]] = []
    seen_ids: set[str] = set()

    def add_asset(tagged: Asset, raw_tag: str, scene_role: str | None, is_root_tag: bool) -> None:
        file_asset = _file_for_tag(assets, tagged, project_dir)
        if file_asset is None or not file_asset.path:
            warnings.append(f"@{tagged.handle or tagged.name} has no file")
            return
        if file_asset.id in seen_ids:
            pending.append((raw_tag, tagged, file_asset, infer_role(file_asset, scene_role), is_root_tag))
            return
        seen_ids.add(file_asset.id)
        pending.append((raw_tag, tagged, file_asset, infer_role(file_asset, scene_role), is_root_tag))

    for raw, handle in parse_tags(text):
        tagged = _resolve_handle(assets, handle)
        if tagged is None:
            unmatched.append(handle)
            continue
        root = root_of(assets, tagged)
        is_root_tag = tagged.id == root.id
        add_asset(tagged, raw, None, is_root_tag)

    if scene:
        for ref in scene.asset_refs:
            asset = asset_by_id(assets, ref.asset_id)
            if asset is None:
                continue
            add_asset(asset, f"@{asset.handle}" if asset.handle else asset.name, ref.role, not asset.parent_asset_id)

    if extra_paths:
        by_path = {str(a.absolute_path(project_dir)): a for a in assets if a.path}
        for path in extra_paths:
            asset = by_path.get(str(path))
            if asset and asset.id not in seen_ids:
                add_asset(asset, f"@{asset.handle}" if asset.handle else asset.name, None, not asset.parent_asset_id)

    bound_files: list[BoundFile] = []
    for raw_tag, tagged, file_asset, role, is_root_tag in pending:
        media = _media_of(file_asset)
        if media is None:
            continue
        if media == "image" and role not in contract.image_roles and role not in {"identity", "first_frame", "last_frame"}:
            if "identity" not in contract.image_roles:
                warnings.append(f"{file_asset.name}: image role {role} not used by this model")
                continue
        if media == "video" and contract.max_videos <= 0:
            warnings.append(f"{file_asset.name}: this model does not take video references")
            continue
        if media == "audio" and contract.max_audio <= 0:
            warnings.append(f"{file_asset.name}: this model does not take audio references")
            continue
        if media == "video" and role not in contract.video_roles and contract.video_roles:
            role = contract.video_roles[0]
        path = file_asset.absolute_path(project_dir)
        bound_files.append(
            BoundFile(
                asset=file_asset,
                root=root_of(assets, file_asset),
                path=path,
                media=media,
                role=role,
                label_kind=_label_kind_for(contract, file_asset, role, is_root_tag),
                tag=raw_tag,
            )
        )

    # unique by path, keep first
    unique: list[BoundFile] = []
    seen_paths: set[str] = set()
    for item in bound_files:
        key = str(item.path)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        unique.append(item)

    ordered: list[BoundFile] = []
    for media in contract.file_order:
        ordered.extend([f for f in unique if f.media == media])

    caps = {
        "image": contract.max_images,
        "video": contract.max_videos,
        "audio": contract.max_audio,
    }
    kept: list[BoundFile] = []
    counts = {"image": 0, "video": 0, "audio": 0}
    for item in ordered:
        if counts[item.media] >= caps[item.media]:
            warnings.append(f"Dropped extra {item.media} ref {item.asset.name} (max {caps[item.media]})")
            continue
        if len(kept) >= contract.max_total:
            warnings.append(f"Dropped extra ref {item.asset.name} (max {contract.max_total} files)")
            continue
        counts[item.media] += 1
        item.slot = counts[item.media]
        item.index = item.slot
        if item.label_kind == "name":
            item.label = item.root.name or item.asset.name
        else:
            item.label = contract.format_label(item.label_kind, item.index) or item.asset.name
        kept.append(item)

    # Subject numbers are per unique root, not per file
    if contract.uses_subject_labels:
        subject_index: dict[str, int] = {}
        next_subject = 1
        for item in kept:
            if item.label_kind != "subject":
                continue
            key = item.root.id
            if key not in subject_index:
                subject_index[key] = next_subject
                next_subject += 1
            item.index = subject_index[key]
            item.label = contract.format_label("subject", item.index)

    tag_labels: dict[str, str] = {}
    replacements: list[tuple[str, str]] = []
    used_raw: set[str] = set()
    for raw, handle in parse_tags(text):
        if raw in used_raw:
            continue
        used_raw.add(raw)
        tagged = _resolve_handle(assets, handle)
        label = ""
        if tagged:
            file_asset = _file_for_tag(assets, tagged, project_dir)
            match = next((f for f in kept if file_asset and f.asset.id == file_asset.id), None)
            if match is None:
                match = next((f for f in kept if f.root.id == root_of(assets, tagged).id), None)
            if match:
                label = match.label
        if label:
            tag_labels[handle] = label
            replacements.append((raw, label))

    rewritten = text or ""
    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)
    for raw, label in replacements:
        rewritten = rewritten.replace(raw, label)

    return BindResult(
        rewritten=rewritten,
        files=kept,
        unmatched=unmatched,
        warnings=warnings,
        contract=contract,
        tag_labels=tag_labels,
    )


def bind_request(request: GenerationRequest, contract: ReferenceContract | None = None) -> BindResult:
    cap = contract
    if cap is None:
        plugin_cap = getattr(request, "plugin_contract", None)
        cap = plugin_cap or ReferenceContract()
    text = request.prompt
    if not text and request.scene:
        text = request.scene.prompt or request.scene.plot_summary
    result = bind_assets(
        text=text or "",
        project=request.project,
        scene=request.scene,
        contract=cap,
        extra_paths=list(request.reference_paths or []),
    )
    request.bound = result
    return result


def ensure_bound(request: GenerationRequest, contract: ReferenceContract, *, strict: bool = False) -> BindResult:
    bound = request.bound
    if bound is None:
        bound = bind_request(request, contract)
    if strict and bound.unmatched:
        tags = ", ".join(f"@{t}" for t in bound.unmatched)
        raise ValueError(f"Unknown asset tags: {tags}")
    return bound
