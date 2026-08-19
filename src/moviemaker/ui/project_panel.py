"""Left-column project panel: create, open, metadata, export."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from moviemaker.core.project import ASPECT_RATIOS, EXPORT_QUALITIES, GENERATE_QUALITIES, PRESETS
from moviemaker.core.state import AppState
from moviemaker.export.upscale import upscaler_choices


def project_panel(state: AppState) -> None:
    @ui.refreshable
    def body() -> None:
        p = state.project
        if p is None:
            ui.label("No project open.").classes("text-sm text-gray-400")
        else:
            name = ui.input("Name", value=p.name).classes("w-full")
            mood = ui.textarea("Mood", value=p.mood).classes("w-full").props("autogrow")
            story = ui.textarea("Base storyline", value=p.base_storyline).classes("w-full").props("autogrow")
            ratio = ui.select(ASPECT_RATIOS, value=p.aspect_ratio, label="Aspect ratio").classes("w-full")
            length = ui.number("Target length (s)", value=p.target_length_seconds, min=3, max=600, step=1)
            fps = ui.number("FPS", value=p.fps, min=8, max=60, step=1)
            gen_q = ui.select(
                {q: q.upper() for q in GENERATE_QUALITIES},
                value=p.generate_quality or "sd",
                label="Generate quality",
            ).classes("w-full")
            exp_q = ui.select(
                {q: q.upper() for q in EXPORT_QUALITIES},
                value=p.export_quality or "hd",
                label="Export quality",
            ).classes("w-full")
            up_on = ui.switch("Upscale on export", value=p.upscale_enabled)
            plugin = state.registry.get(p.default_model_id)
            methods = upscaler_choices(state.installed_upscalers, plugin.capabilities.reference)
            up_method = ui.select(
                methods,
                value=p.upscale_method if p.upscale_method in methods else next(iter(methods)),
                label="Upscaler",
            ).classes("w-full")
            ui.label("Draft cheap, then upscale finished clips. This does not re-render the scene.").classes(
                "text-xs text-gray-500"
            )

            def save_meta() -> None:
                p.name = str(name.value)
                p.mood = str(mood.value or "")
                p.base_storyline = str(story.value or "")
                p.aspect_ratio = str(ratio.value)
                p.target_length_seconds = float(length.value or 30)
                p.fps = float(fps.value or 24)
                p.generate_quality = str(gen_q.value or "sd")
                p.export_quality = str(exp_q.value or "hd")
                p.upscale_enabled = bool(up_on.value)
                p.upscale_method = str(up_method.value or "")
                state.persist_project()
                ui.notify("Project saved")
                state.emit()

            ui.button("Save project", on_click=save_meta).props("unelevated").classes("w-full")

        with ui.row().classes("w-full"):
            ui.button("New", on_click=lambda: _new_dialog(state, body)).props("outline dense")
            ui.button("Open", on_click=lambda: _open_dialog(state, body)).props("outline dense")
            ui.button("ZIP out", on_click=lambda: _zip_out(state)).props("outline dense")
            ui.button("ZIP in", on_click=lambda: _zip_in(state, body)).props("outline dense")

        if p:
            async def do_export() -> None:
                await _export(state)

            ui.button("Export movie", on_click=do_export).props("unelevated").classes("w-full")
            ui.label(p.project_dir).classes("text-xs text-gray-500 break-all")

    body()
    state.subscribe(body.refresh)


async def _export(state: AppState) -> None:
    try:
        ui.notify("Exporting…")
        path = await state.export_movie()
        ui.notify(f"Exported {path}")
    except Exception as exc:
        ui.notify(str(exc), type="negative")


def _zip_out(state: AppState) -> None:
    try:
        path = state.export_project_zip()
        ui.notify(f"Wrote {path}")
    except Exception as exc:
        ui.notify(str(exc), type="negative")


def _zip_in(state: AppState, body) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[520px] mm-card"):
        ui.label("Import project ZIP").classes("text-lg")
        archive = ui.input("ZIP file path").classes("w-full")
        dest = ui.input("Destination folder", value=str(state.settings.default_projects_dir / "imported")).classes("w-full")

        def go() -> None:
            try:
                state.import_project_zip(Path(str(archive.value)), Path(str(dest.value)))
                dialog.close()
                body.refresh()
            except Exception as exc:
                ui.notify(str(exc), type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Import", on_click=go).props("unelevated")
    dialog.open()


def _new_dialog(state: AppState, body) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[520px] mm-card"):
        ui.label("Create project").classes("text-lg")
        folder = ui.input("Empty folder", value=str(state.settings.default_projects_dir / "new_movie")).classes("w-full")
        name = ui.input("Name", value="Untitled").classes("w-full")
        preset = ui.select({k: v["label"] for k, v in PRESETS.items()}, value="blank", label="Preset").classes("w-full")
        mood = ui.input("Mood").classes("w-full")
        story = ui.textarea("Storyline").classes("w-full")
        ratio = ui.select(ASPECT_RATIOS, value="16:9", label="Aspect").classes("w-full")
        length = ui.number("Target seconds", value=30, min=5, max=600)

        def create() -> None:
            try:
                state.new_project(
                    Path(str(folder.value)),
                    str(name.value or "Untitled"),
                    mood=str(mood.value or ""),
                    base_storyline=str(story.value or ""),
                    aspect_ratio=str(ratio.value),
                    target_length_seconds=float(length.value or 30),
                    preset=str(preset.value or "blank"),
                )
                dialog.close()
                body.refresh()
            except Exception as exc:
                ui.notify(str(exc), type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Create", on_click=create).props("unelevated")
    dialog.open()


def _open_dialog(state: AppState, body) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[480px] mm-card"):
        ui.label("Open project").classes("text-lg")
        folder = ui.input("Project folder", value=str(state.settings.default_projects_dir)).classes("w-full")

        def open_it() -> None:
            try:
                state.open_project(Path(str(folder.value)))
                dialog.close()
                body.refresh()
            except Exception as exc:
                ui.notify(str(exc), type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Open", on_click=open_it).props("unelevated")
    dialog.open()
