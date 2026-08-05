"""Load plugins from plugins/ directory (YAML/JSON manifest + optional module)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from gnom_hub.plugins.registry import ToolRegistry, ToolSpec


class PluginLoader:
    def __init__(self, plugins_dir: Path, registry: ToolRegistry) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.registry = registry
        self.loaded: list[dict[str, Any]] = []

    def discover_and_load(self) -> list[dict[str, Any]]:
        self.loaded = []
        if not self.plugins_dir.is_dir():
            return self.loaded
        for child in sorted(self.plugins_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest = child / "plugin.json"
            if not manifest.is_file():
                continue
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if meta.get("enabled") is False:
                continue
            info = {
                "id": meta.get("id") or child.name,
                "name": meta.get("name") or child.name,
                "version": meta.get("version") or "0.0.0",
                "path": str(child),
            }
            # Register tools declared in manifest
            for t in meta.get("tools") or []:
                name = t.get("name")
                if not name:
                    continue
                handler_name = t.get("handler", "run")
                mod_path = child / (t.get("module") or "main.py")
                handler = self._load_handler(mod_path, handler_name)
                if handler is None:
                    continue
                self.registry.register(
                    ToolSpec(
                        name=name,
                        description=t.get("description") or name,
                        handler=handler,
                        input_schema=t.get("input_schema") or {},
                        plugin=info["id"],
                    )
                )
            self.loaded.append(info)
        return self.loaded

    def _load_handler(self, path: Path, attr: str):
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(f"gnom_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:  # noqa: BLE001
            return None
        return getattr(mod, attr, None)
