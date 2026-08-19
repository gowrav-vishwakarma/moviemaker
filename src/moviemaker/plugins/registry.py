"""Discover plugin packages and bind them to Wan2GP architectures."""

from __future__ import annotations

from typing import Any

from moviemaker.backend.wan2gp_catalog import CatalogEntry, Wan2GPCatalog
from moviemaker.plugins.base import Capability, ModelPlugin
from moviemaker.plugins.flux.plugin import FluxPlugin
from moviemaker.plugins.generic.plugin import GenericPlugin
from moviemaker.plugins.ltx2.plugin import Ltx2Plugin
from moviemaker.plugins.minimax_h3.plugin import MiniMaxH3Plugin
from moviemaker.plugins.qwen_image_edit.plugin import QwenImageEditPlugin
from moviemaker.plugins.wan.plugin import WanPlugin


class PluginRegistry:
    def __init__(self) -> None:
        self.plugins: dict[str, ModelPlugin] = {}
        self.architecture_map: dict[str, str] = {}
        self.generic = GenericPlugin()

    def register(self, plugin: ModelPlugin) -> None:
        self.plugins[plugin.id] = plugin
        for arch in plugin.capabilities.architectures:
            self.architecture_map[arch] = plugin.id

    def bind(self, catalog: Wan2GPCatalog | None, client: Any) -> None:
        self.generic.bind(catalog, client)
        for plugin in self.plugins.values():
            bind = getattr(plugin, "bind", None)
            if callable(bind):
                bind(catalog, client)

    def for_architecture(self, architecture: str) -> ModelPlugin:
        plugin_id = self.architecture_map.get(architecture)
        if plugin_id:
            return self.plugins[plugin_id]
        arch = architecture.lower()
        if arch.startswith("minimax_h3"):
            return self.plugins.get("minimax_h3", self.generic)
        if arch.startswith("ltx2") or arch.startswith("ltxv"):
            return self.plugins.get("ltx2", self.generic)
        if arch.startswith(("t2v", "i2v", "ti2v", "wan")):
            return self.plugins.get("wan", self.generic)
        if "flux" in arch:
            return self.plugins.get("flux", self.generic)
        if arch.startswith("qwen_image"):
            return self.plugins.get("qwen_image_edit", self.generic)
        return self.generic

    def get(self, plugin_id: str) -> ModelPlugin:
        if plugin_id in self.plugins:
            return self.plugins[plugin_id]
        if plugin_id == "generic":
            return self.generic
        return self.generic

    def list_plugins(self, kind: str | None = None) -> list[ModelPlugin]:
        items: list[ModelPlugin] = [self.generic, *self.plugins.values()]
        if kind:
            items = [p for p in items if p.capabilities.kind == kind or p.id == "generic"]
        # unique by id, dedicated plugins first except generic last for video
        seen: set[str] = set()
        ordered: list[ModelPlugin] = []
        for plugin in items:
            if plugin.id in seen:
                continue
            seen.add(plugin.id)
            ordered.append(plugin)
        return ordered

    def plugin_for_entry(self, entry: CatalogEntry) -> ModelPlugin:
        return self.for_architecture(entry.architecture)

    def video_choices(self, catalog: Wan2GPCatalog | None) -> list[tuple[str, str, str]]:
        """Return (plugin_id, model_type, label) for scene model dropdowns."""
        choices: list[tuple[str, str, str]] = []
        if catalog:
            for entry in catalog.list_entries("video"):
                plugin = self.plugin_for_entry(entry)
                choices.append((plugin.id, entry.model_type, f"{entry.name} · {plugin.id}"))
        if not choices:
            for plugin in self.list_plugins("video"):
                model_type = plugin.capabilities.vram_tiers[0].model_type if plugin.capabilities.vram_tiers else plugin.id
                choices.append((plugin.id, model_type, plugin.capabilities.name))
        return choices

    def image_choices(self, catalog: Wan2GPCatalog | None) -> list[tuple[str, str, str]]:
        choices: list[tuple[str, str, str]] = []
        if catalog:
            for entry in catalog.list_entries("image"):
                plugin = self.plugin_for_entry(entry)
                choices.append((plugin.id, entry.model_type, f"{entry.name} · {plugin.id}"))
        if not choices:
            for plugin in self.list_plugins("image"):
                model_type = plugin.capabilities.vram_tiers[0].model_type if plugin.capabilities.vram_tiers else plugin.id
                choices.append((plugin.id, model_type, plugin.capabilities.name))
        return choices

    def capabilities_for(self, plugin_id: str, model_type: str | None, catalog: Wan2GPCatalog | None) -> Capability:
        plugin = self.get(plugin_id)
        if plugin.id == "generic" and catalog and model_type:
            entry = catalog.get(model_type)
            if entry:
                return self.generic.capabilities_for(entry.architecture, image=entry.image_outputs)
        return plugin.capabilities


def build_registry() -> PluginRegistry:
    registry = PluginRegistry()
    for plugin in (MiniMaxH3Plugin(), WanPlugin(), Ltx2Plugin(), FluxPlugin(), QwenImageEditPlugin()):
        registry.register(plugin)
    return registry
