"""Application settings dialog (Wan2GP path, Ollama, hardware)."""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from moviemaker.core.hardware import detect_hardware
from moviemaker.core.state import AppState
from moviemaker.settings import looks_like_wan2gp


def open_settings(state: AppState) -> None:
    s = state.settings
    with ui.dialog() as dialog, ui.card().classes("w-[640px] mm-card"):
        ui.label("Application settings").classes("text-lg font-medium")
        ui.label("These are not stored in the project — they apply to this machine.").classes("text-xs text-gray-400")
        wan = ui.input("Wan2GP path", value=str(s.wan2gp_path or "")).classes("w-full")
        ollama_host = ui.input("Ollama host", value=s.ollama_host).classes("w-full")
        ollama_model = ui.input("Ollama model", value=s.ollama_model).classes("w-full")
        projects = ui.input("Default projects folder", value=str(s.default_projects_dir)).classes("w-full")
        with ui.row().classes("items-center gap-4"):
            mock = ui.switch("Use mock backend", value=s.use_mock_backend)
            dry = ui.switch("Dry-run by default", value=s.dry_run_by_default)
            low = ui.switch("Low-VRAM mode", value=s.hardware_profile.low_vram_mode)
        vram = ui.number("VRAM (GB)", value=s.hardware_profile.vram_gb, min=0, max=128, step=0.5)
        ram = ui.number("System RAM (GB)", value=s.hardware_profile.system_ram_gb, min=0, max=512, step=1)
        gpu = ui.input("GPU name", value=s.hardware_profile.gpu_name).classes("w-full")

        def redetect() -> None:
            hw = detect_hardware()
            vram.value = hw.vram_gb
            ram.value = hw.system_ram_gb
            gpu.value = hw.gpu_name
            ui.notify(f"Detected {hw.gpu_name} · {hw.vram_gb} GB")

        def save() -> None:
            path = Path(str(wan.value or "")).expanduser()
            s.wan2gp_path = path if str(wan.value).strip() else None
            if s.wan2gp_path and not looks_like_wan2gp(s.wan2gp_path):
                ui.notify("That folder does not look like Wan2GP (need wgp.py + env/bin/python)", type="warning")
            s.ollama_host = str(ollama_host.value)
            s.ollama_model = str(ollama_model.value)
            s.default_projects_dir = Path(str(projects.value)).expanduser()
            s.use_mock_backend = bool(mock.value)
            s.dry_run_by_default = bool(dry.value)
            s.hardware_profile.low_vram_mode = bool(low.value)
            s.hardware_profile.vram_gb = float(vram.value or 0)
            s.hardware_profile.system_ram_gb = float(ram.value or 0)
            s.hardware_profile.gpu_name = str(gpu.value or "Unknown")
            state.persist_settings()
            ui.notify("Settings saved")
            dialog.close()

        with ui.row().classes("w-full justify-between"):
            ui.button("Re-detect GPU", on_click=redetect).props("flat")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save).props("unelevated")
    dialog.open()
