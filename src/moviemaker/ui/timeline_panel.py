"""NLE-style timeline: time ruler, fixed track labels, positioned clips."""

from __future__ import annotations

from nicegui import ui

from moviemaker.core.state import AppState
from moviemaker.core.timeline import Clip


def _tick_step(total: float) -> float:
    for step in (1, 2, 5, 10, 15, 30, 60, 120, 300):
        if total / step <= 12:
            return float(step)
    return 600.0


def timeline_panel(state: AppState) -> None:
    @ui.refreshable
    def body() -> None:
        if state.project is None:
            with ui.element("div").classes("mm-panel-head"):
                ui.label("Timeline")
            with ui.element("div").classes("mm-panel-body"):
                ui.label("Timeline appears once a project is open.").classes("text-sm text-gray-400")
            return

        total = max(state.project.total_duration(), state.project.target_length_seconds, 1.0)

        with ui.element("div").classes("mm-panel-head"):
            ui.label("Timeline")
            ui.label(f"{total:g}s · {len(state.project.scenes)} scenes · {state.project.fps:g} fps").classes(
                "normal-case tracking-normal text-xs"
            )

        with ui.element("div").classes("mm-panel-body").style("padding:8px 10px"):
            # Ruler: left spacer aligns with the track-label column, then ticks.
            with ui.row().classes("w-full no-wrap gap-0 items-stretch"):
                ui.element("div").style("width:120px;flex:0 0 120px")
                with ui.element("div").classes("mm-tl-ruler grow"):
                    step = _tick_step(total)
                    t = 0.0
                    while t <= total + 0.001:
                        left = 100.0 * t / total
                        with ui.element("div").classes("mm-tl-tick").style(f"left:{left:.3f}%"):
                            ui.label(f"{t:g}s")
                        t += step

            for layer in state.project.layers:
                with ui.element("div").classes("mm-tl-row w-full no-wrap"):
                    muted = " muted" if layer.muted else ""
                    with ui.element("div").classes(f"mm-tl-label{muted}"):
                        ui.label(layer.name).classes("truncate")
                        ui.button(
                            icon="volume_off" if layer.muted else "volume_up",
                            on_click=lambda l=layer: _toggle_mute(state, l.id),
                        ).props("flat round dense size=sm")
                    with ui.element("div").classes("mm-track"):
                        for clip in layer.clips:
                            left = 100.0 * clip.start_time_seconds / total
                            width = max(2.0, 100.0 * clip.effective_duration / total)
                            active = clip.scene_id and clip.scene_id == state.selected_scene_id
                            klass = f"mm-clip {layer.type}" + (" active" if active else "")
                            with ui.element("div").classes(klass).style(
                                f"left:{left:.3f}%;width:{width:.3f}%"
                            ).on("click", lambda c=clip: _click_clip(state, c)):
                                ui.label(clip.label or clip.id).classes("text-[10px] leading-none")

            addable = [l for l in state.project.layers if l.type != "video"]
            if addable:
                with ui.row().classes("w-full gap-2 mt-2 no-wrap items-center"):
                    ui.label("Add selected asset to:").classes("text-xs text-gray-500")
                    for layer in addable:
                        ui.button(
                            layer.name,
                            icon="add",
                            on_click=lambda l=layer: _add_clip(state, l.id),
                        ).props("outline dense size=sm")

    body()
    state.subscribe(body.refresh)


def _toggle_mute(state: AppState, layer_id: str) -> None:
    if not state.project:
        return
    for layer in state.project.layers:
        if layer.id == layer_id:
            layer.muted = not layer.muted
    state.persist_project()
    state.emit()


def _click_clip(state: AppState, clip: Clip) -> None:
    if clip.scene_id:
        state.select_scene(clip.scene_id)
    if clip.asset_id:
        state.selected_asset_id = clip.asset_id
    state.emit()


def _add_clip(state: AppState, layer_id: str) -> None:
    if not state.project or not state.selected_asset:
        ui.notify("Select an asset first", type="warning")
        return
    layer = next(l for l in state.project.layers if l.id == layer_id)
    start = layer.total_duration()
    layer.clips.append(
        Clip(
            asset_id=state.selected_asset.id,
            start_time_seconds=start,
            duration_seconds=5.0,
            label=state.selected_asset.name,
        )
    )
    state.persist_project()
    state.emit()
