"""Asset Studio dialog: image-kind plugins, multi-reference, PIL ops."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from moviemaker.asset_studio.studio import enqueue_image_job, pil_edit
from moviemaker.core.state import AppState


def open_asset_studio(state: AppState) -> None:
    if state.project is None:
        ui.notify("Open a project first", type="warning")
        return
    choices = state.registry.image_choices(state.catalog)
    labels = {f"{plugin}|{model}": label for plugin, model, label in choices} or {"flux|flux_krea": "Flux (mock)"}
    refs: list[str] = []

    with ui.dialog() as dialog, ui.card().classes("w-[720px] max-h-[90vh] overflow-auto mm-card"):
        ui.label("Asset Studio").classes("text-lg font-medium")
        ui.label("Image plugins generate or edit stills. Attach multiple references when the model allows it.").classes(
            "text-xs text-gray-400"
        )
        model = ui.select(labels, value=next(iter(labels)), label="Model").classes("w-full")
        prompt = ui.textarea("Prompt / edit instruction", placeholder="a product hero on black marble, 85mm, soft rim light").classes(
            "w-full"
        )
        mention_map = {a.handle: f"@{a.handle}  {a.name}" for a in state.project.assets if a.handle}
        mention = ui.select({"": "Insert @asset…"} | mention_map, value="").classes("w-full")

        def insert_mention(e) -> None:
            handle = str(getattr(e, "value", "") or "")
            if not handle:
                return
            current = str(prompt.value or "")
            spacer = "" if current.endswith(" ") or not current else " "
            prompt.value = f"{current}{spacer}@{handle} "
            mention.value = ""

        mention.on("update:model-value", insert_mention)
        name = ui.input("Asset name", value="generated_asset").classes("w-full")
        kind = ui.select(["subject", "prop", "background", "style_ref", "other"], value="subject", label="Map as").classes("w-full")
        steps = ui.number("Steps", value=20, min=1, max=50)
        guidance = ui.number("Guidance", value=3.5, min=0, max=15, step=0.1)
        seed = ui.number("Seed", value=-1, min=-1, step=1)
        size = ui.select(["1024x1024", "1280x720", "720x1280", "1328x1328"], value="1024x1024", label="Size").classes("w-full")
        parent = ui.select(
            {"": "(none — generate new)"}
            | {a.id: f"{a.name} ({a.mapped_name})" for a in state.project.assets if a.type == "image"},
            value="",
            label="Edit parent",
        ).classes("w-full")

        ui.label("Reference images").classes("text-sm mt-2")
        ref_box = ui.column().classes("w-full gap-1")

        def render_refs() -> None:
            ref_box.clear()
            with ref_box:
                if not refs:
                    ui.label("None selected").classes("text-xs text-gray-500")
                for asset_id in refs:
                    asset = state.project.get_asset(asset_id) if state.project else None
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(asset.name if asset else asset_id)
                        ui.button("Remove", on_click=lambda i=asset_id: _drop(i)).props("flat dense")

        def _drop(asset_id: str) -> None:
            if asset_id in refs:
                refs.remove(asset_id)
            render_refs()

        def add_ref(asset_id: str | None) -> None:
            if asset_id and asset_id not in refs:
                refs.append(asset_id)
            render_refs()

        add_sel = ui.select(
            {a.id: a.name for a in state.project.assets if a.type == "image"},
            label="Add reference",
            on_change=lambda e: add_ref(e.value),
        ).classes("w-full")
        render_refs()

        def generate() -> None:
            plugin_id, model_type = str(model.value).split("|", 1)
            ref_paths: list[Path] = []
            if state.project:
                for asset_id in refs:
                    asset = state.project.get_asset(asset_id)
                    if asset:
                        ref_paths.append(asset.absolute_path(state.project.dir()))
                if parent.value:
                    parent_asset = state.project.get_asset(str(parent.value))
                    if parent_asset:
                        path = parent_asset.absolute_path(state.project.dir())
                        if path not in ref_paths:
                            ref_paths.insert(0, path)
            state.queue.start()
            enqueue_image_job(
                project=state.project,
                registry=state.registry,
                queue=state.queue,
                settings=state.settings,
                plugin_id=plugin_id,
                model_type=model_type,
                prompt=str(prompt.value or ""),
                options={
                    "num_inference_steps": int(steps.value or 20),
                    "guidance_scale": float(guidance.value or 3.5),
                    "seed": int(seed.value or -1),
                    "resolution": str(size.value),
                },
                reference_paths=ref_paths,
                name=str(name.value or "generated"),
                mapped_kind=str(kind.value),
                parent_asset_id=str(parent.value) or None,
                on_complete=lambda _a: ui.notify("Asset generated"),
            )
            ui.notify("Image job queued")
            dialog.close()
            state.emit()

        with ui.row().classes("w-full justify-end"):
            ui.button("Close", on_click=dialog.close).props("flat")
            ui.button("Generate", on_click=generate).props("unelevated")

        if state.selected_asset and state.selected_asset.type == "image":
            ui.separator()
            ui.label("PIL ops on selected asset").classes("text-sm")
            with ui.row():
                for op, label in [
                    ("rotate_90", "90°"),
                    ("rotate_180", "180°"),
                    ("flip_h", "Flip H"),
                    ("flip_v", "Flip V"),
                ]:
                    ui.button(label, on_click=lambda o=op: _pil(state, o, dialog)).props("outline dense")
    dialog.open()


def _pil(state: AppState, op: str, dialog) -> None:
    if state.project is None or state.selected_asset is None:
        return
    pil_edit(state.project, state.selected_asset, op)  # type: ignore[arg-type]
    ui.notify(f"Applied {op}")
    dialog.close()
    state.emit()
