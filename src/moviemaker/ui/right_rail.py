"""Right dock: scene list, or the selected scene's properties editor."""

from __future__ import annotations

from nicegui import ui

from moviemaker.core.state import AppState
from moviemaker.ui.scene_properties_panel import render_scene_properties
from moviemaker.ui.story_plot_panel import render_scene_list


def right_rail(state: AppState) -> None:
    @ui.refreshable
    def body() -> None:
        editing = state.editing_scene and state.selected_scene is not None
        with ui.element("div").classes("mm-panel-head"):
            if editing:
                with ui.row().classes("items-center gap-2"):
                    ui.button(icon="arrow_back", on_click=state.close_scene_editor).props(
                        "flat round dense size=sm"
                    ).tooltip("Back to scenes")
                    ui.label("Scene")
                ui.label(state.selected_scene.title).classes("normal-case tracking-normal text-xs")
            else:
                ui.label("Story · Scenes")
                if state.project:
                    ui.label(f"{len(state.project.scenes)} scenes").classes(
                        "normal-case tracking-normal text-xs"
                    )
        with ui.element("div").classes("mm-panel-body"):
            if editing:
                render_scene_properties(state)
            else:
                render_scene_list(state)

    body()
    state.subscribe(body.refresh)
