"""Editing-suite layout: collapsible project drawer, media bin, program monitor,
scene rail, and a full-width timeline docked at the bottom."""

from __future__ import annotations

from nicegui import ui

from moviemaker.core.state import AppState
from moviemaker.ui.assets_panel import assets_panel
from moviemaker.ui.player_panel import player_panel
from moviemaker.ui.project_panel import project_panel
from moviemaker.ui.right_rail import right_rail
from moviemaker.ui.settings_dialog import open_settings
from moviemaker.ui.theme import inject_theme
from moviemaker.ui.timeline_panel import timeline_panel


def _panel(title: str, width_style: str = "", grow: bool = False):
    classes = "mm-panel h-full"
    if grow:
        classes += " grow"
    style = "min-width:0;min-height:0;"
    if width_style:
        style += width_style
    return ui.element("div").classes(classes).style(style)


def build_layout(state: AppState) -> None:
    inject_theme()

    with ui.left_drawer(value=False, bordered=True).props("width=340 behavior=desktop").classes(
        "p-2"
    ) as project_drawer:
        with ui.element("div").classes("mm-panel h-full"):
            with ui.element("div").classes("mm-panel-head"):
                ui.label("Project")
                ui.button(icon="chevron_left", on_click=project_drawer.toggle).props("flat round dense size=sm")
            with ui.element("div").classes("mm-panel-body"):
                project_panel(state)

    with ui.header().classes("mm-header items-center justify-between px-3 py-1"):
        with ui.row().classes("items-center gap-3"):
            ui.button(icon="tune", on_click=project_drawer.toggle).props("flat round dense").tooltip(
                "Project settings"
            )
            ui.label("MOVIE MAKER").classes("mm-brand text-xs font-semibold")
            name = state.project.name if state.project else "No project"
            ui.label(name).classes("text-base font-medium")
        with ui.row().classes("items-center gap-3"):
            hw = state.hardware
            backend = "mock" if state.settings.use_mock_backend or not state.settings.wan2gp_ready() else "Wan2GP"
            ui.label(
                f"{hw.gpu_name} · {hw.vram_gb:g} GB · {backend} · {len(state.catalog.entries)} models"
            ).classes("text-xs").style("color:#6b7583")
            ui.button(icon="settings", on_click=lambda: open_settings(state)).props("flat round dense")

    with ui.column().classes("w-full no-wrap gap-2 p-2").style(
        "height: calc(100vh - 100px); background: var(--mm-bg)"
    ):
        with ui.row().classes("w-full no-wrap gap-2 grow items-stretch").style("min-height:0"):
            with _panel("Media", width_style="width:320px;flex:0 0 320px;"):
                with ui.element("div").classes("mm-panel-head"):
                    ui.label("Media bin")
                with ui.element("div").classes("mm-panel-body"):
                    assets_panel(state)
            with ui.column().classes("h-full grow gap-2").style("min-width:0"):
                with ui.element("div").classes("mm-panel grow w-full").style("min-height:0"):
                    with ui.element("div").classes("mm-panel-head"):
                        ui.label("Program monitor")
                    with ui.element("div").classes("mm-panel-body"):
                        player_panel(state)
            with _panel("Scenes", width_style="width:440px;flex:0 0 440px;"):
                right_rail(state)

        with ui.element("div").classes("mm-panel w-full").style("height:250px;flex:0 0 250px"):
            timeline_panel(state)

    with ui.footer().classes("px-4 py-2 text-xs").style(
        "background:#ffffff;border-top:1px solid var(--mm-border);color:#6b7583"
    ):
        status = ui.label(state.status_message)

        def refresh_status() -> None:
            status.set_text(state.status_message)

        state.subscribe(refresh_status)
