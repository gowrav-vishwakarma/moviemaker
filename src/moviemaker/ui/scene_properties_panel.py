"""Right-column scene properties: model, prompts, camera, assets, generate."""

from __future__ import annotations

from nicegui import ui

from moviemaker.core.scene import CAMERA_PRESETS, CAMERA_SPEEDS, AssetRef
from moviemaker.core.state import AppState
from moviemaker.plugins.tagging import bind_assets, parse_tags


def render_scene_properties(state: AppState) -> None:
    if True:
        scene = state.selected_scene
        if scene is None or state.project is None:
            ui.label("Select a scene from the story panel.").classes("text-sm text-gray-400")
            _queue_list(state)
            return

        title = ui.input("Title", value=scene.title).classes("w-full")
        plot = ui.textarea("Plot (story view)", value=scene.plot_summary).classes("w-full").props("autogrow")
        duration = ui.number("Duration (s)", value=scene.duration_seconds, min=1, max=30, step=1)

        choices = state.registry.video_choices(state.catalog)
        option_map = {f"{pid}|{mt}": label for pid, mt, label in choices}
        current_key = f"{scene.model_id}|{scene.model_type_override or state.project.default_model_type or ''}"
        if current_key not in option_map and option_map:
            current_key = next(iter(option_map))
        model = ui.select(option_map or {"generic|": "Generic"}, value=current_key, label="Model").classes("w-full")

        plugin = state.registry.get(scene.model_id)
        tier = plugin.select_tier(state.hardware)
        quants = ["", "bf16", "int8", "fp8", "gguf_q8", "gguf_q4"]
        entry = state.catalog.get(scene.model_type_override or "") if scene.model_type_override else None
        if entry:
            quants = [""] + entry.quantizations
        quant = ui.select(
            {q: (q or f"auto ({tier.quantization or 'default'})") for q in quants},
            value=scene.quantization_override or "",
            label="Quantization override",
        ).classes("w-full")
        ui.label(f"Hardware pick: {tier.label} · {tier.model_type or 'catalog'} · {tier.quantization}").classes(
            "text-xs text-gray-500"
        )

        prompt = ui.textarea("Prompt  (tag assets with @handle)", value=scene.prompt).classes("w-full").props("autogrow")
        mention_map = {a.handle: f"@{a.handle}  {a.name}" for a in state.project.assets if a.handle}
        mention = ui.select({"": "Insert @asset…"} | mention_map, value="", label="Insert tag").classes("w-full")

        def insert_mention(e) -> None:
            handle = str(e.value or "")
            if not handle:
                return
            current = str(prompt.value or "")
            spacer = "" if current.endswith(" ") or not current else " "
            prompt.value = f"{current}{spacer}@{handle} "
            mention.value = ""
            _render_chips()

        mention.on("update:model-value", insert_mention)
        chip_box = ui.row().classes("w-full flex-wrap gap-1")
        hint = ui.label("").classes("text-xs text-gray-500")

        def _render_chips() -> None:
            scene.prompt = str(prompt.value or "")
            chip_box.clear()
            text = str(prompt.value or "")
            tags = parse_tags(text)
            bound = bind_assets(
                text=text,
                project=state.project,
                scene=scene,
                contract=plugin.capabilities.reference,
            )
            with chip_box:
                if not tags:
                    ui.label(f"Tags rewrite to {plugin.capabilities.reference.syntax_hint}").classes(
                        "text-xs text-gray-500"
                    )
                for _raw, handle in tags:
                    label = bound.tag_labels.get(handle)
                    color = "positive" if label else "negative"
                    ui.badge(f"@{handle}" + (f" → {label}" if label else " ?")).props(f"color={color}")
            extra = []
            if bound.unmatched:
                extra.append("Unknown: " + ", ".join(f"@{t}" for t in bound.unmatched))
            extra.extend(bound.warnings)
            hint.text = " · ".join(extra)

        prompt.on("update:model-value", lambda _e: _render_chips())
        _render_chips()

        negative = ui.textarea("Negative prompt", value=scene.negative_prompt).classes("w-full").props("autogrow")
        camera = ui.select(list(CAMERA_PRESETS.keys()), value=scene.camera_motion, label="Camera").classes("w-full")
        speed = ui.select(list(CAMERA_SPEEDS.keys()), value=scene.camera_speed, label="Speed").classes("w-full")
        custom = ui.textarea("Custom camera notes", value=scene.camera_custom).classes("w-full")

        ui.label("Asset roles").classes("text-sm mt-2")
        assets = {a.id: f"{a.name} (@{a.handle})" for a in state.project.assets}
        first = ui.select(
            {"": "—"} | assets,
            value=_role_asset(scene, "first_frame"),
            label="First frame",
        ).classes("w-full")
        last = ui.select({"": "—"} | assets, value=_role_asset(scene, "last_frame"), label="Last frame").classes("w-full")
        subject = ui.select({"": "—"} | assets, value=_role_asset(scene, "subject"), label="Subject").classes("w-full")
        contract = plugin.capabilities.reference
        video_sel = None
        video_role = None
        if contract.max_videos > 0:
            videos = {a.id: f"{a.name} (@{a.handle})" for a in state.project.assets if a.type == "video"}
            video_sel = ui.select(
                {"": "—"} | videos,
                value=_role_asset(scene, "motion") or _role_asset(scene, "camera") or _role_asset(scene, "edit_source"),
                label="Video reference",
            ).classes("w-full")
            roles = contract.video_roles or ["motion"]
            current_role = "motion"
            for role in roles:
                if _role_asset(scene, role):
                    current_role = role
                    break
            video_role = ui.select(roles, value=current_role, label="Video contributes").classes("w-full")
        else:
            ui.label("This model does not take video references.").classes("text-xs text-gray-500")

        steps = ui.number(
            "Steps",
            value=scene.model_options_override.get("num_inference_steps", plugin.capabilities.default_options.get("num_inference_steps", 8)),
            min=1,
            max=50,
        )
        guidance = ui.number(
            "Guidance",
            value=scene.model_options_override.get("guidance_scale", plugin.capabilities.default_options.get("guidance_scale", 1.0)),
            min=0,
            max=15,
            step=0.1,
        )
        seed = ui.number("Seed", value=scene.model_options_override.get("seed", -1), min=-1, step=1)

        def save() -> None:
            scene.title = str(title.value)
            scene.plot_summary = str(plot.value or "")
            scene.duration_seconds = float(duration.value or 5)
            raw = str(model.value or "generic|")
            pid, _, mt = raw.partition("|")
            scene.model_id = pid or "generic"
            scene.model_type_override = mt or None
            scene.quantization_override = str(quant.value) or None
            scene.prompt = str(prompt.value or "")
            scene.negative_prompt = str(negative.value or "")
            scene.camera_motion = str(camera.value)
            scene.camera_speed = str(speed.value)
            scene.camera_custom = str(custom.value or "")
            scene.model_options_override["num_inference_steps"] = int(steps.value or 8)
            scene.model_options_override["guidance_scale"] = float(guidance.value or 1)
            scene.model_options_override["seed"] = int(seed.value or -1)
            _set_role(scene, "first_frame", str(first.value or ""))
            _set_role(scene, "last_frame", str(last.value or ""))
            _set_role(scene, "subject", str(subject.value or ""))
            for role in ("motion", "camera", "edit_source", "pose"):
                scene.asset_refs = [r for r in scene.asset_refs if r.role != role]
            if video_sel is not None and video_role is not None and video_sel.value:
                _set_role(scene, str(video_role.value or "motion"), str(video_sel.value))
            state.project.sync_timeline()
            state.persist_project()
            ui.notify("Scene saved")
            state.emit()

        with ui.row().classes("w-full flex-wrap"):
            ui.button("Save", on_click=save).props("unelevated")
            ui.button("Preview prompt", on_click=lambda: _preview(state)).props("outline")
            ui.button("Generate", on_click=lambda: _gen(state, False, False)).props("unelevated")
            ui.button("Dry-run", on_click=lambda: _gen(state, True, False)).props("outline")
            ui.button("Extend", on_click=lambda: _gen(state, False, True)).props("outline")
            ui.button("Batch same model", on_click=lambda: _batch(state)).props("outline")

        if scene.error:
            ui.label(scene.error).classes("text-xs text-red-400")
        if scene.generation_log:
            with ui.expansion("Generation log", icon="article").classes("w-full"):
                ui.code(scene.generation_log[-3000:]).classes("w-full text-xs")
        _queue_list(state)


def _queue_list(state: AppState) -> None:
    ui.label("Queue").classes("mm-title mt-3")
    if not state.queue.jobs:
        ui.label("Idle").classes("text-xs text-gray-500")
        return
    for job in state.queue.jobs[:12]:
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"{job.label} · {job.status}").classes("text-xs")
            with ui.row():
                if job.status in {"pending", "running"}:
                    ui.button("Cancel", on_click=lambda j=job: state.queue.cancel(j.id)).props("flat dense")
                if job.status in {"failed", "cancelled"}:
                    ui.button("Retry", on_click=lambda j=job: state.queue.retry(j.id)).props("flat dense")


def _role_asset(scene, role: str) -> str:
    for ref in scene.asset_refs:
        if ref.role == role:
            return ref.asset_id
    return ""


def _set_role(scene, role: str, asset_id: str) -> None:
    scene.asset_refs = [r for r in scene.asset_refs if r.role != role]
    if asset_id:
        scene.asset_refs.append(AssetRef(asset_id=asset_id, role=role))  # type: ignore[arg-type]


def _preview(state: AppState) -> None:
    text = state.preview_prompt()
    with ui.dialog() as dialog, ui.card().classes("w-[640px] max-h-[80vh] overflow-auto mm-card"):
        ui.label("Model prompt").classes("text-lg")
        ui.code(text or "(empty)").classes("w-full text-xs")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _gen(state: AppState, dry_run: bool, extend: bool) -> None:
    try:
        state.generate_selected(dry_run=dry_run, extend=extend)
    except Exception as exc:
        ui.notify(str(exc), type="negative")


def _batch(state: AppState) -> None:
    try:
        state.generate_same_model_batch()
    except Exception as exc:
        ui.notify(str(exc), type="negative")
