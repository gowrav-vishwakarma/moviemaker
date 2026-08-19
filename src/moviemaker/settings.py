"""Application-level settings and Wan2GP auto-detection."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from moviemaker.core.hardware import HardwareProfile, detect_hardware

WAN2GP_PROBE_PATHS = [
    Path("/home/gowrav/pinokio/api/wan.git/app"),
    Path("/media/gowrav/d_drive/pinokio/api/wan.git/app"),
    Path.home() / "pinokio/api/wan.git/app",
    Path.home() / "pinokio/api/Wan2GP/app",
    Path.home() / "Wan2GP",
    Path.home() / "wan2gp",
    Path("/opt/wan2gp"),
]


def default_config_dir() -> Path:
    xdg = Path.home() / ".config" / "moviemaker"
    xdg.mkdir(parents=True, exist_ok=True)
    return xdg


def default_projects_dir() -> Path:
    path = Path.home() / "Movies" / "MovieMaker"
    path.mkdir(parents=True, exist_ok=True)
    return path


def looks_like_wan2gp(root: Path) -> bool:
    return (root / "wgp.py").is_file() and (
        (root / "env" / "bin" / "python").is_file() or (root / "env" / "Scripts" / "python.exe").is_file()
    )


def wan2gp_python(root: Path) -> Path | None:
    posix = root / "env" / "bin" / "python"
    win = root / "env" / "Scripts" / "python.exe"
    if posix.is_file():
        return posix
    if win.is_file():
        return win
    return None


def detect_wan2gp_path() -> Path | None:
    for candidate in WAN2GP_PROBE_PATHS:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if looks_like_wan2gp(resolved):
            return resolved
    return None


class AppSettings(BaseModel):
    wan2gp_path: Path | None = None
    wan2gp_python: Path | None = None
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    default_projects_dir: Path = Field(default_factory=default_projects_dir)
    hardware_profile: HardwareProfile = Field(default_factory=HardwareProfile)
    use_mock_backend: bool = False
    dry_run_by_default: bool = False
    ui_port: int = 8088

    def resolved_wan2gp_python(self) -> Path | None:
        if self.wan2gp_python and Path(self.wan2gp_python).is_file():
            return Path(self.wan2gp_python)
        if self.wan2gp_path:
            return wan2gp_python(Path(self.wan2gp_path))
        return None

    def wan2gp_ready(self) -> bool:
        path = self.wan2gp_path
        py = self.resolved_wan2gp_python()
        return bool(path and Path(path).is_dir() and py and py.is_file() and (Path(path) / "wgp.py").is_file())


def settings_path() -> Path:
    return default_config_dir() / "settings.json"


def apply_auto_detect(settings: AppSettings, *, force_hardware: bool = False) -> AppSettings:
    if settings.wan2gp_path is None or not Path(settings.wan2gp_path).exists():
        found = detect_wan2gp_path()
        if found:
            settings.wan2gp_path = found
            settings.wan2gp_python = wan2gp_python(found)
    elif settings.wan2gp_python is None:
        settings.wan2gp_python = wan2gp_python(Path(settings.wan2gp_path))
    if force_hardware or settings.hardware_profile.vram_gb <= 0:
        detected = detect_hardware()
        detected.low_vram_mode = settings.hardware_profile.low_vram_mode
        detected.prefers_cpu_offload = settings.hardware_profile.prefers_cpu_offload
        if settings.hardware_profile.vram_gb <= 0:
            settings.hardware_profile = detected
        else:
            settings.hardware_profile.gpu_name = settings.hardware_profile.gpu_name or detected.gpu_name
            settings.hardware_profile.system_ram_gb = (
                settings.hardware_profile.system_ram_gb or detected.system_ram_gb
            )
            settings.hardware_profile.cuda_version = (
                settings.hardware_profile.cuda_version or detected.cuda_version
            )
    if not settings.wan2gp_ready():
        settings.use_mock_backend = True
    return settings


def load_settings() -> AppSettings:
    path = settings_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = AppSettings.model_validate(data)
    else:
        settings = AppSettings()
    settings = apply_auto_detect(settings)
    save_settings(settings)
    return settings


def save_settings(settings: AppSettings) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(settings.model_dump_json())
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
