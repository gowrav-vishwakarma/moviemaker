"""Shared plugin runner that talks to Wan2GP or the mock backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from moviemaker.backend.wan2gp_catalog import Wan2GPCatalog
from moviemaker.core.hardware import HardwareProfile
from moviemaker.plugins.base import Capability, GenerationRequest, GenerationResult, VramTier
from moviemaker.plugins.settings_common import apply_catalog_defaults, base_settings


class BasePlugin:
    id: str = "base"
    capabilities: Capability
    catalog: Wan2GPCatalog | None = None
    client: Any = None

    def bind(self, catalog: Wan2GPCatalog | None, client: Any) -> None:
        self.catalog = catalog
        self.client = client

    def is_available(self, hardware: HardwareProfile, catalog: Any) -> bool:
        if not self.capabilities.vram_tiers:
            return True
        return any(hardware.effective_vram_gb() >= t.min_vram_gb or t.min_vram_gb == 0 for t in self.capabilities.vram_tiers)

    def select_tier(self, hardware: HardwareProfile) -> VramTier:
        vram = hardware.effective_vram_gb()
        viable = [t for t in self.capabilities.vram_tiers if vram >= t.min_vram_gb]
        if not viable:
            return min(self.capabilities.vram_tiers, key=lambda t: t.min_vram_gb)
        viable.sort(key=lambda t: t.recommended_vram_gb)
        for tier in reversed(viable):
            if vram >= tier.recommended_vram_gb:
                return tier
        return viable[0]

    def build_prompt(self, request: GenerationRequest) -> str:
        from moviemaker.plugins.tagging import ensure_bound

        ensure_bound(request, self.capabilities.reference, strict=False)
        if request.prompt:
            return request.bound.rewritten if request.bound and request.bound.rewritten else request.prompt
        if request.scene:
            return request.scene.prompt or request.scene.plot_summary
        return ""

    def build_negative_prompt(self, request: GenerationRequest) -> str | None:
        if request.negative_prompt:
            return request.negative_prompt
        if request.scene and request.scene.negative_prompt:
            return request.scene.negative_prompt
        return None

    def build_wan2gp_settings(self, request: GenerationRequest, prompt: str) -> dict[str, Any]:
        request.negative_prompt = self.build_negative_prompt(request)
        settings = base_settings(request, prompt, fps=self.capabilities.fps)
        return apply_catalog_defaults(settings, self.catalog, request.model_type)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        from moviemaker.plugins.tagging import ensure_bound

        if self.client is None:
            return GenerationResult(status="failed", error="No generation backend bound to plugin")
        ensure_bound(request, self.capabilities.reference, strict=True)
        prompt = self.build_prompt(request)
        settings = self.build_wan2gp_settings(request, prompt)
        return await self.client.process(
            settings,
            request.output_dir,
            dry_run=request.dry_run,
            log_path=request.log_path,
            on_progress=request.on_progress,
            cancel_event=request.cancel_event,
        )

    async def extend(self, existing: Path, request: GenerationRequest) -> GenerationResult:
        from moviemaker.plugins.tagging import ensure_bound

        ensure_bound(request, self.capabilities.reference, strict=True)
        prompt = self.build_prompt(request)
        settings = self.build_wan2gp_settings(request, prompt)
        settings["video_source"] = str(existing)
        if self.client is None:
            return GenerationResult(status="failed", error="No generation backend bound to plugin")
        return await self.client.process(
            settings,
            request.output_dir,
            dry_run=request.dry_run,
            log_path=request.log_path,
            on_progress=request.on_progress,
            cancel_event=request.cancel_event,
        )
