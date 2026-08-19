"""Assets panel: tree, handles, variants, URL clip import."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from moviemaker.core.asset import set_default_child, walk_tree
from moviemaker.core.state import AppState
from moviemaker.ui.asset_editor_dialog import open_asset_studio


KIND_OPTIONS = ["subject", "prop", "background", "style_ref", "motion_ref", "audio", "other"]
VARIANT_OPTIONS = ["default", "pose", "outfit", "expression", "angle", "still", "clip", "other"]


def assets_panel(state: AppState) -> None:
    @ui.refreshable
    def body() -> None:
        if state.project is None:
            ui.label("Open a project to add assets.").classes("text-sm text-gray-400")
            return
        ui.upload(
            label="Upload image / video / audio",
            auto_upload=True,
            on_upload=lambda e: _on_upload(state, e, body),
        ).props("accept=image/*,video/*,audio/* dense").classes("w-full")
        with ui.row().classes("w-full"):
            ui.button("Asset Studio", on_click=lambda: open_asset_studio(state)).props("unelevated").classes("flex-1")
            ui.button("From URL", on_click=lambda: _url_dialog(state, body)).props("outline").classes("flex-1")
        for asset, depth in walk_tree(state.project.assets):
            selected = asset.id == state.selected_asset_id
            pad = 8 + depth * 14
            with ui.card().classes("w-full mm-scene-card" + (" active" if selected else "")).style(
                f"margin-left:{pad}px"
            ).on("click", lambda a=asset: _select(state, a.id, body)):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(asset.name).classes("text-sm font-medium")
                    ui.label(f"@{asset.handle}").classes("text-xs").style("color:#c47b17")
                bits = [asset.type, asset.source, asset.variant_kind]
                if asset.is_default and asset.parent_asset_id:
                    bits.append("default")
                ui.label(" · ".join(bits)).classes("text-xs text-gray-500")
                if selected:
                    name = ui.input("Name", value=asset.name).classes("w-full")
                    handle = ui.input("Handle (@tag)", value=asset.handle).classes("w-full")
                    kind = ui.select(KIND_OPTIONS, value=asset.mapped_kind, label="Map as").classes("w-full")
                    variant = ui.select(VARIANT_OPTIONS, value=asset.variant_kind, label="Variant").classes("w-full")

                    def save_map(a=asset, n=name, h=handle, k=kind, v=variant) -> None:
                        from moviemaker.core.asset import rename_handle

                        a.name = str(n.value or a.name)
                        a.mapped_kind = k.value  # type: ignore[assignment]
                        a.variant_kind = v.value  # type: ignore[assignment]
                        new_handle = str(h.value or a.handle)
                        if new_handle != a.handle:
                            rename_handle(state.project.assets, a, new_handle)
                        state.persist_project()
                        ui.notify("Asset saved")
                        body.refresh()

                    with ui.row().classes("w-full flex-wrap"):
                        ui.button("Save", on_click=save_map).props("flat dense")
                        if asset.parent_asset_id:
                            ui.button("Set default", on_click=lambda a=asset: _make_default(state, a, body)).props("flat dense")
                        ui.button("Add variant", on_click=lambda a=asset: _variant_dialog(state, a.id, body)).props(
                            "flat dense"
                        )
                thumb = asset.absolute_path(state.project.dir())
                if asset.type == "image" and thumb.exists():
                    ui.image(str(thumb)).classes("w-full rounded-md max-h-28 object-cover")

    body()
    state.subscribe(body.refresh)


def _select(state: AppState, asset_id: str, body) -> None:
    state.selected_asset_id = asset_id
    body.refresh()


def _make_default(state: AppState, asset, body) -> None:
    if state.project is None:
        return
    set_default_child(state.project.assets, asset)
    state.persist_project()
    body.refresh()


async def _on_upload(state: AppState, event, body, parent_id: str | None = None, variant_kind: str = "default") -> None:
    if state.project is None:
        return
    upload = getattr(event, "file", event)
    name = getattr(upload, "name", None) or getattr(event, "name", "upload.bin")
    dest = state.project.tmp_dir() / name
    if hasattr(upload, "save"):
        await upload.save(dest)
    else:
        content = getattr(event, "content", None)
        dest.write_bytes(content.read() if content else b"")
    state.add_uploaded_asset(dest, Path(name).stem, parent_id=parent_id, variant_kind=variant_kind)
    dest.unlink(missing_ok=True)
    body.refresh()
    ui.notify(f"Added {name}")


def _variant_dialog(state: AppState, parent_id: str, body) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[480px] mm-card"):
        ui.label("Add variant").classes("text-lg")
        kind = ui.select(VARIANT_OPTIONS, value="outfit", label="Variant kind").classes("w-full")
        name = ui.input("Name", value="red").classes("w-full")
        ui.upload(
            label="Upload file",
            auto_upload=True,
            on_upload=lambda e: _variant_upload(state, e, parent_id, str(kind.value), str(name.value), dialog, body),
        ).props("accept=image/*,video/*,audio/* dense").classes("w-full")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


async def _variant_upload(state: AppState, event, parent_id: str, variant_kind: str, name: str, dialog, body) -> None:
    await _on_upload(state, event, body, parent_id=parent_id, variant_kind=variant_kind or "other")
    if state.selected_asset and name:
        state.selected_asset.name = name
        from moviemaker.core.asset import rename_handle

        if state.project:
            rename_handle(state.project.assets, state.selected_asset, name)
            state.persist_project()
    dialog.close()
    body.refresh()


def _url_dialog(state: AppState, body) -> None:
    if state.project is None:
        return
    parents = {"": "(none — top level)"} | {a.id: f"{a.name} (@{a.handle})" for a in state.project.assets if not a.parent_asset_id}
    with ui.dialog() as dialog, ui.card().classes("w-[520px] mm-card"):
        ui.label("Import timed clip").classes("text-lg")
        ui.label("YouTube or any yt-dlp URL. Clips are capped at 15 seconds.").classes("text-xs text-gray-500")
        url = ui.input("URL").classes("w-full")
        start = ui.input("From", value="0:00").classes("w-full")
        end = ui.input("To", value="0:08").classes("w-full")
        name = ui.input("Asset name", value="ref_clip").classes("w-full")
        parent = ui.select(parents, value="", label="Parent character").classes("w-full")

        def go() -> None:
            try:
                state.import_url_clip(
                    str(url.value or ""),
                    str(name.value or "ref_clip"),
                    str(start.value or "0"),
                    str(end.value or "8"),
                    parent_id=str(parent.value or "") or None,
                )
                dialog.close()
                body.refresh()
                ui.notify("Clip imported")
            except Exception as exc:
                ui.notify(str(exc), type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Download", on_click=go).props("unelevated")
    dialog.open()
