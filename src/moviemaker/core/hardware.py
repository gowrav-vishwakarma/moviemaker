"""Hardware profile detection (VRAM, RAM, GPU, CUDA)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any

from pydantic import BaseModel, Field


class HardwareProfile(BaseModel):
    vram_gb: float = 0.0
    system_ram_gb: float = 0.0
    gpu_name: str = "Unknown"
    cuda_version: str | None = None
    os: str = Field(default_factory=lambda: platform.system().lower())
    low_vram_mode: bool = False
    prefers_cpu_offload: bool = False

    def effective_vram_gb(self) -> float:
        if self.low_vram_mode:
            return min(self.vram_gb, 8.0) if self.vram_gb else 8.0
        return self.vram_gb


def _run(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if result.returncode == 0:
            return (result.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def _detect_ram_gb() -> float:
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        phys = os.sysconf("SC_PHYS_PAGES")
        return round((page * phys) / (1024**3), 1)
    except (ValueError, OSError, AttributeError):
        pass
    if os.path.exists("/proc/meminfo"):
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    kb = float(line.split()[1])
                    return round(kb / (1024**2), 1)
    return 0.0


def _detect_nvidia() -> tuple[str, float, str | None]:
    if not shutil.which("nvidia-smi"):
        return "Unknown", 0.0, None
    raw = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not raw:
        return "Unknown", 0.0, None
    first = raw.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    name = parts[0] if parts else "Unknown"
    vram = 0.0
    driver = None
    if len(parts) > 1:
        try:
            mi_or_gb = float(parts[1])
            vram = round(mi_or_gb / 1024.0, 1) if mi_or_gb > 64 else mi_or_gb
        except ValueError:
            vram = 0.0
    if len(parts) > 2:
        driver = parts[2]
    cuda = None
    version_raw = _run(["nvidia-smi"])
    if version_raw:
        for token in version_raw.split():
            if token.startswith("CUDA"):
                continue
        if "CUDA Version:" in version_raw:
            try:
                cuda = version_raw.split("CUDA Version:")[1].split()[0]
            except IndexError:
                cuda = driver
    return name, vram, cuda or driver


def detect_hardware() -> HardwareProfile:
    gpu_name, vram_gb, cuda = _detect_nvidia()
    ram = _detect_ram_gb()
    low = vram_gb > 0 and vram_gb < 12
    return HardwareProfile(
        vram_gb=vram_gb,
        system_ram_gb=ram,
        gpu_name=gpu_name,
        cuda_version=cuda,
        os=platform.system().lower(),
        low_vram_mode=low,
        prefers_cpu_offload=vram_gb > 0 and vram_gb < 10,
    )


def profile_to_dict(profile: HardwareProfile) -> dict[str, Any]:
    return profile.model_dump()
