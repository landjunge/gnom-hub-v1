"""Load plugins from plugins/ directory (JSON manifest + optional module).

Security note (local desk):
  Loading a plugin runs its ``main.py`` (or declared module) via
  ``importlib.exec_module`` — arbitrary Python at import time.
  Only install plugins you trust. Do not treat third-party packs as safe
  without review. God-Mode / computer-use remain separate gates.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

from gnom_hub.plugins.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)


class PluginLoader:
    def __init__(self, plugins_dir: Path, registry: ToolRegistry) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.registry = registry
        self.loaded: list[dict[str, Any]] = []
        self.errors: list[dict[str, str]] = []

    def discover_and_load(self) -> list[dict[str, Any]]:
        self.loaded = []
        self.errors = []
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
            except json.JSONDecodeError as exc:
                msg = f"invalid plugin.json: {exc}"
                logger.warning("Plugin %s skipped — %s", child.name, msg)
                self.errors.append({"path": str(child), "error": msg})
                continue
            except OSError as exc:
                msg = f"cannot read plugin.json: {exc}"
                logger.warning("Plugin %s skipped — %s", child.name, msg)
                self.errors.append({"path": str(child), "error": msg})
                continue

            if not isinstance(meta, dict):
                msg = "plugin.json root must be an object"
                logger.warning("Plugin %s skipped — %s", child.name, msg)
                self.errors.append({"path": str(child), "error": msg})
                continue

            if meta.get("enabled") is False:
                logger.debug("Plugin %s disabled in manifest", child.name)
                continue

            info = {
                "id": str(meta.get("id") or child.name),
                "name": str(meta.get("name") or child.name),
                "version": str(meta.get("version") or "0.0.0"),
                "path": str(child),
            }
            tools = meta.get("tools") or []
            if tools is not None and not isinstance(tools, list):
                msg = "tools must be a list"
                logger.warning("Plugin %s skipped — %s", child.name, msg)
                self.errors.append({"path": str(child), "error": msg})
                continue

            registered = 0
            for t in tools:
                if not isinstance(t, dict):
                    logger.warning(
                        "Plugin %s: skip non-object tool entry",
                        info["id"],
                    )
                    continue
                name = t.get("name")
                if not name or not isinstance(name, str):
                    logger.warning(
                        "Plugin %s: tool missing string name",
                        info["id"],
                    )
                    continue
                handler_name = str(t.get("handler") or "run")
                mod_file = str(t.get("module") or "main.py")
                # no path escape outside plugin dir
                mod_path = (child / mod_file).resolve()
                try:
                    mod_path.relative_to(child.resolve())
                except ValueError:
                    msg = f"module path escapes plugin dir: {mod_file}"
                    logger.warning("Plugin %s: %s", info["id"], msg)
                    self.errors.append({"path": str(child), "error": msg})
                    continue

                handler = self._load_handler(mod_path, handler_name, info["id"])
                if handler is None:
                    continue
                schema = t.get("input_schema") or {}
                if not isinstance(schema, dict):
                    schema = {}
                self.registry.register(
                    ToolSpec(
                        name=name,
                        description=str(t.get("description") or name),
                        handler=handler,
                        input_schema=schema,
                        plugin=info["id"],
                    )
                )
                registered += 1

            if registered == 0 and tools:
                msg = "no tools registered (handlers failed or empty names)"
                logger.warning("Plugin %s: %s", info["id"], msg)
                self.errors.append({"path": str(child), "error": msg})
                continue

            self.loaded.append(info)
            logger.info(
                "Plugin loaded: %s v%s (%d tools)",
                info["id"],
                info["version"],
                registered,
            )
        return self.loaded

    def _load_handler(self, path: Path, attr: str, plugin_id: str):
        if not path.is_file():
            logger.warning(
                "Plugin %s: module file missing: %s",
                plugin_id,
                path,
            )
            return None
        spec = importlib.util.spec_from_file_location(f"gnom_plugin_{plugin_id}_{path.stem}", path)
        if spec is None or spec.loader is None:
            logger.warning(
                "Plugin %s: cannot create import spec for %s",
                plugin_id,
                path,
            )
            return None
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            logger.exception(
                "Plugin %s: failed to exec module %s",
                plugin_id,
                path,
            )
            self.errors.append(
                {
                    "path": str(path),
                    "error": f"exec_module failed for {path.name}",
                }
            )
            return None
        handler = getattr(mod, attr, None)
        if handler is None:
            logger.warning(
                "Plugin %s: attribute %r not found in %s",
                plugin_id,
                attr,
                path.name,
            )
        return handler
