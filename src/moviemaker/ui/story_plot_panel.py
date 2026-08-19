"""Scene rail: one-line story generator + compact scene cards."""

from __future__ import annotations

from nicegui import ui

from moviemaker.core.state import AppState
from moviemaker.story.generator import apply_story, generate_story

_STATUS_DOT = {
    "done": "mm-dot-done",
    "ready": "mm-dot-done",
    "running": "mm-dot-run",
    "generating": "mm-dot-run",
    "failed": "mm-dot-fail",
    "error": "mm-dot-fail",
}


def render_scene_list(state: AppState) -> None:
    if state.project is None:
        ui.label("Create or open a project.").classes("text-sm text-gray-400")
        return

    idea = ui.textarea(
        "One-line idea",
        value=state.project.base_storyline,
        placeholder="A late-night jazz duo, rain on the windows, one missed call",
    ).classes("w-full").props("autogrow dense")

    async def run_story() -> None:
        try:
            ui.notify("Talking to Ollama…")
            story = await generate_story(str(idea.value or ""), state.project, state.settings)
            apply_story(state.project, story, state.project.default_model_id)
            if state.project.scenes:
                state.selected_scene_id = state.project.scenes[0].id
            state.persist_project()
            state.emit()
            ui.notify(f"Wrote {len(state.project.scenes)} scenes")
        except Exception as exc:
            ui.notify(str(exc), type="negative")

    with ui.row().classes("w-full gap-2 no-wrap"):
        ui.button("Generate story", on_click=run_story).props("unelevated dense").classes("grow")
        ui.button(icon="add", on_click=lambda: state.add_scene()).props("outline dense").tooltip("Add scene")
        ui.button(icon="movie_filter", on_click=lambda: _gen_all(state)).props("outline dense").tooltip(
            "Generate all scenes"
        )

    if not state.project.scenes:
        ui.label("No scenes yet. Generate a story or add a scene.").classes(
            "text-sm text-gray-400 mt-2"
        )
        return

    for index, scene in enumerate(state.project.scenes, start=1):
        active = scene.id == state.selected_scene_id
        with ui.element("div").classes("w-full mm-scene-card" + (" active" if active else "")).on(
            "click", lambda s=scene: state.select_scene(s.id)
        ):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.label(str(index)).classes("mm-chip-num")
                with ui.column().classes("grow gap-0").style("min-width:0"):
                    ui.label(scene.title).classes("text-sm font-medium truncate")
                    with ui.row().classes("items-center gap-1"):
                        dot = _STATUS_DOT.get(scene.status, "mm-dot-idle")
                        ui.element("span").classes(f"mm-status-dot {dot}")
                        ui.label(f"{scene.duration_seconds:g}s · {scene.status}").classes(
                            "text-xs text-gray-500"
                        )
                ui.button(
                    icon="tune",
                    on_click=lambda s=scene: state.open_scene_editor(s.id),
                ).props("flat round dense size=sm").tooltip("Edit scene")
            summary = scene.plot_summary or scene.prompt
            if summary:
                ui.label(summary).classes("text-xs text-gray-500 truncate")
            with ui.row().classes("gap-0"):
                ui.button(icon="keyboard_arrow_up", on_click=lambda s=scene: state.move_scene(s.id, -1)).props(
                    "flat dense size=sm"
                )
                ui.button(icon="keyboard_arrow_down", on_click=lambda s=scene: state.move_scene(s.id, 1)).props(
                    "flat dense size=sm"
                )
                ui.button(icon="delete", on_click=lambda s=scene: state.delete_scene(s.id)).props(
                    "flat dense size=sm"
                )


def _gen_all(state: AppState) -> None:
    try:
        state.generate_scenes()
    except Exception as exc:
        ui.notify(str(exc), type="negative")
