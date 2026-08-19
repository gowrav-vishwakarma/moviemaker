"""Program monitor: scene clip, selected media, or full-timeline export."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from moviemaker.core.state import AppState


def player_panel(state: AppState) -> None:
    @ui.refreshable
    def body() -> None:
        with ui.column().classes("h-full w-full no-wrap gap-2").style("min-height:0"):
            with ui.row().classes("w-full items-center justify-between no-wrap"):
                with ui.row().classes("items-center gap-2"):
                    ui.button("Scene", icon="movie", on_click=lambda: _play_scene(state, body)).props(
                        "outline dense"
                    )
                    ui.button(
                        "Full timeline", icon="playlist_play", on_click=lambda: _play_full(state, body)
                    ).props("outline dense")
                src = state.play_source
                if src:
                    ui.label(f"{state.play_mode} · {Path(src).name}").classes(
                        "text-xs text-gray-500 truncate"
                    )

            with ui.element("div").classes("mm-monitor w-full grow").style("min-height:0"):
                src = state.play_source
                if src and Path(src).exists():
                    suffix = Path(src).suffix.lower()
                    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                        ui.image(src).classes("max-w-full max-h-full object-contain")
                    else:
                        ui.video(src).classes("max-w-full max-h-full").props("controls")
                else:
                    with ui.column().classes("items-center gap-2").style("color:#8a93a0"):
                        ui.icon("smart_display", size="42px")
                        ui.label("Nothing to play yet").classes("text-sm")

            scene = state.selected_scene
            if scene:
                ui.label(f"Scene: {scene.title} · {scene.duration_seconds:g}s").classes(
                    "text-xs text-gray-500 w-full text-center shrink-0"
                )

    body()
    state.subscribe(body.refresh)


def _play_scene(state: AppState, body) -> None:
    scene = state.selected_scene
    if scene and scene.output_path:
        state.play_source = scene.output_path
        state.play_mode = "scene"
        body.refresh()
    else:
        ui.notify("Generate this scene first", type="warning")


async def _play_full(state: AppState, body) -> None:
    if state.last_export and state.last_export.exists():
        state.play_source = str(state.last_export)
        state.play_mode = "full"
        body.refresh()
        return
    try:
        ui.notify("Exporting…")
        path = await state.export_movie(crossfade=0.0)
        state.play_source = str(path)
        state.play_mode = "full"
        body.refresh()
    except Exception as exc:
        ui.notify(str(exc), type="negative")
