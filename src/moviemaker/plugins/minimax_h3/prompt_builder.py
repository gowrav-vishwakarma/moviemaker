"""MiniMax H3 native prompt builder (timed shot list + official reference labels)."""

from __future__ import annotations

from collections import defaultdict

from moviemaker.core.scene import Scene
from moviemaker.plugins.base import GenerationRequest
from moviemaker.plugins.reference import h3_contract
from moviemaker.plugins.tagging import BindResult, BoundFile, ensure_bound


def _shot_windows(duration: float) -> list[tuple[float, float]]:
    if duration <= 4:
        return [(0, duration)]
    if duration <= 8:
        mid = round(duration * 0.4, 1)
        return [(0, mid), (mid, duration)]
    a = round(duration * 0.3, 1)
    b = round(duration * 0.7, 1)
    return [(0, a), (a, b), (b, duration)]


def _retention_marker(item: BoundFile) -> str:
    if item.role in {"first_frame", "last_frame"}:
        return "fully_preserved"
    if item.role in {"wardrobe", "pose", "style"}:
        return "attribute_transfer"
    if item.media == "video":
        return "partially_preserved"
    if item.media == "audio":
        return "reference"
    return "fully_preserved"


def _subject_definitions(bound: BindResult) -> list[str]:
    groups: dict[str, list[BoundFile]] = defaultdict(list)
    for item in bound.files:
        groups[item.root.id].append(item)
    lines: list[str] = []
    seen_roots: set[str] = set()
    for item in bound.files:
        if item.root.id in seen_roots:
            continue
        seen_roots.add(item.root.id)
        members = groups[item.root.id]
        pictures = [m for m in members if m.media == "image"]
        videos = [m for m in members if m.media == "video"]
        audios = [m for m in members if m.media == "audio"]
        name = item.root.name
        kind = item.root.mapped_kind
        if item.label_kind == "subject" or kind in {"subject", "prop", "background", "style_ref"}:
            subject = next((m.label for m in members if m.label_kind == "subject"), None)
            if subject is None and bound.contract.subject_label:
                # still define as subject using first picture index
                subject = bound.contract.format_label("subject", len(lines) + 1)
            bits = [f"{subject or name} is {name}"]
            if kind == "background":
                bits.append("the setting / environment")
            elif kind == "prop":
                bits.append("the hero object")
            elif kind == "style_ref":
                bits.append("the look / grade")
            else:
                bits.append("the performer / identity")
            if pictures:
                pic_labels = " and ".join(
                    bound.contract.format_label("picture", p.slot) or p.label for p in pictures
                )
                bits.append(f"whose appearance comes from {pic_labels}")
            if videos:
                vid_labels = " and ".join(v.label for v in videos if v.label)
                role = videos[0].role
                bits.append(f"whose {role} comes from {vid_labels}")
            lines.append(", ".join(bits) + ".")
        for pic in pictures:
            if pic.role in {"first_frame", "last_frame"}:
                where = "first frame" if pic.role == "first_frame" else "last frame"
                lines.append(f"{pic.label} is the {where} of [Shot 1], showing {name}.")
        for vid in videos:
            if item.label_kind != "subject":
                lines.append(f"{vid.label} is the source video for {vid.role.replace('_', ' ')}.")
        for audio in audios:
            lines.append(f"{audio.label} is a {audio.role} reference for {name}.")
    return lines


def _timed_body(request: GenerationRequest, body: str) -> str:
    scene: Scene | None = request.scene
    duration = scene.duration_seconds if scene else 5.0
    windows = _shot_windows(duration)
    if "\n[" in body or body.startswith("["):
        shots = [body]
    else:
        sentences = [s.strip() for s in body.replace(".", ".\n").splitlines() if s.strip()]
        if not sentences:
            sentences = [body or "Cinematic scene."]
        shots = []
        for i, (start, end) in enumerate(windows):
            piece = sentences[i] if i < len(sentences) else sentences[-1]
            shots.append(f"[{start:g}-{end:g}s] {piece}")
    camera = scene.camera_phrase() if scene else ""
    if camera:
        shots.append(f"Camera throughout: {camera}.")
    return "\n".join(shots)


def build_minimax_prompt(request: GenerationRequest) -> str:
    bound = ensure_bound(request, h3_contract(), strict=False)
    scene: Scene | None = request.scene
    raw = (request.prompt or (scene.prompt if scene else "") or (scene.plot_summary if scene else "")).strip()
    body = bound.rewritten.strip() if bound.rewritten else raw
    shots = _timed_body(request, body)
    audio_notes = [
        "overall_soundscape: natural room tone matching the location, realistic stereo acoustics",
        "non_diegetic_music: subtle, supporting, never drowning dialogue",
    ]
    if scene and scene.plot_summary:
        audio_notes.append(f"story beat: {scene.plot_summary.strip()}")
    if not bound.files:
        return f"Shots:\n{shots}\n\nAudio:\n" + "\n".join(audio_notes)

    defs = _subject_definitions(bound) or ["Referenced assets as uploaded."]
    retention = []
    for item in bound.files:
        marker = _retention_marker(item)
        retention.append(f"{item.label}: {marker}")
    summary = "[reference generation] Generate a target video that follows the tagged assets in playback order."
    if scene and scene.title:
        summary += f" Scene: {scene.title}."
    return "\n\n".join(
        [
            "subject_definitions:\n" + "\n".join(defs),
            f"summary: {summary}",
            "retention_analysis:\n" + "\n".join(retention),
            "detailed_description:\n" + shots,
            audio_notes[0],
            audio_notes[1],
        ]
    )
