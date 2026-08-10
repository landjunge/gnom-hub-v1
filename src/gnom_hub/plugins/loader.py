"""Load plugins from plugins/ directory (JSON manifest + optional module).

Security note (local desk):
  Loading a plugin runs its ``main.py`` (or declared module) via
  ``importlib.exec_module`` — arbitrary Python at import time.
  Only install plugins you trust. Do not treat third-party packs as safe
  without review. God-Mode / computer-use remain separate gates.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import logging
from pathlib import Path
from typing import Any

from gnom_hub.plugins.manifest import ManifestError, validate_manifest
from gnom_hub.plugins.registry import ToolRegistry, ToolSpec

logger = logging.getLogger(__name__)

_LOAD_SEQ = itertools.count(1)


class PluginLoader:
    def __init__(self, plugins_dir: Path, registry: ToolRegistry) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.registry = registry
        self.loaded: list[dict[str, Any]] = []
        self.errors: list[dict[str, str]] = []

    def reload_all(self) -> dict[str, Any]:
        """Hot-reload all plugins from disk (unregister non-core, re-discover)."""
        removed = []
        if hasattr(self.registry, "unregister_non_core"):
            removed = self.registry.unregister_non_core()
        self.loaded = []
        self.errors = []
        loaded = self.discover_and_load()
        logger.info("Plugins reloaded: %d plugins, removed_tools=%s", len(loaded), removed)
        return {
            "ok": True,
            "plugins": loaded,
            "removed_tools": list(removed or []),
            "errors": list(self.errors),
        }

    def discover_and_load(self) -> list[dict[str, Any]]:
        self.loaded = []
        self.errors = []
        if not self.plugins_dir.is_dir():
            return self.loaded
        for child in sorted(self.plugins_dir.iterdir()):
            if not child.is_dir():
                continue
            # skip templates / private folders
            if child.name.startswith(("_", ".")):
                continue
            manifest = child / "plugin.json"
            if not manifest.is_file():
                continue
            self._load_one(child, manifest)
        return self.loaded

    def scan_disk(self) -> list[dict[str, Any]]:
        """
        Inventory of plugins/ folders (drop-in discovery, no load side effects).

        Status: loaded | disabled | error | no_manifest | empty.
        Lets the desk show what is on disk vs what actually registered.
        """
        out: list[dict[str, Any]] = []
        if not self.plugins_dir.is_dir():
            return out
        loaded_by_id = {str(p.get("id") or ""): p for p in self.loaded}
        error_plugins = {str(e.get("plugin") or e.get("path") or "") for e in (self.errors or [])}
        for child in sorted(self.plugins_dir.iterdir()):
            if not child.is_dir() or child.name.startswith(("_", ".")):
                continue
            manifest = child / "plugin.json"
            entry: dict[str, Any] = {
                "folder": child.name,
                "path": str(child),
                "has_manifest": manifest.is_file(),
            }
            if not manifest.is_file():
                entry["status"] = "no_manifest"
                entry["id"] = child.name
                out.append(entry)
                continue
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                entry["status"] = "error"
                entry["id"] = child.name
                entry["error"] = f"invalid plugin.json: {exc}"
                out.append(entry)
                continue
            if not isinstance(meta, dict):
                entry["status"] = "error"
                entry["id"] = child.name
                entry["error"] = "plugin.json must be an object"
                out.append(entry)
                continue
            pid = str(meta.get("id") or child.name).strip() or child.name
            entry["id"] = pid
            entry["name"] = str(meta.get("name") or pid)
            entry["version"] = str(meta.get("version") or "")
            entry["description"] = str(meta.get("description") or "")[:200]
            enabled = meta.get("enabled", True)
            if isinstance(enabled, str):
                enabled = enabled.strip().lower() not in ("0", "false", "no", "off")
            entry["enabled"] = bool(enabled)
            tools_raw = meta.get("tools") if isinstance(meta.get("tools"), list) else []
            entry["tool_count_declared"] = len(tools_raw)
            if pid in loaded_by_id:
                entry["status"] = "loaded"
                entry["tool_count"] = loaded_by_id[pid].get("tool_count") or len(
                    loaded_by_id[pid].get("tools") or []
                )
            elif not entry["enabled"]:
                entry["status"] = "disabled"
            elif pid in error_plugins or child.name in error_plugins:
                entry["status"] = "error"
                for e in self.errors or []:
                    if pid in str(e.get("plugin") or "") or child.name in str(e.get("path") or ""):
                        entry["error"] = str(e.get("error") or "load failed")[:200]
                        break
            else:
                entry["status"] = "not_loaded"
            out.append(entry)
        return out

    def reload(self, plugin_id: str) -> dict[str, Any]:
        """
        Re-read one plugin folder and re-register its tools (overwrite same plugin).

        Unregisters previous tools that still point at this plugin id, then loads again.
        """
        pid = (plugin_id or "").strip()
        if not pid:
            return {"ok": False, "error": "plugin_id required"}
        # drop existing tools from this plugin
        for name in list(self.registry.names()):
            spec = self.registry.get(name)
            if spec and spec.plugin == pid:
                self.registry.unregister(name, force=True)
        self.loaded = [p for p in self.loaded if p.get("id") != pid]
        self.errors = [
            e for e in self.errors if e.get("plugin") != pid and pid not in str(e.get("path") or "")
        ]

        child = self.plugins_dir / pid
        # also match folder by id in plugin.json
        if not child.is_dir():
            for cand in sorted(self.plugins_dir.iterdir()):
                if not cand.is_dir() or cand.name.startswith(("_", ".")):
                    continue
                mj = cand / "plugin.json"
                if not mj.is_file():
                    continue
                try:
                    meta = json.loads(mj.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if str(meta.get("id") or cand.name) == pid:
                    child = cand
                    break
        manifest = child / "plugin.json"
        if not child.is_dir() or not manifest.is_file():
            return {"ok": False, "error": f"plugin not found: {pid}"}
        before = len(self.loaded)
        self._load_one(child, manifest)
        ok = any(p.get("id") == pid for p in self.loaded)
        return {
            "ok": ok,
            "plugin_id": pid,
            "loaded_delta": len(self.loaded) - before,
            "tools": [t for p in self.loaded if p.get("id") == pid for t in p.get("tools") or []],
            "errors": [e for e in self.errors if pid in str(e)],
        }

    def _load_one(self, child: Path, manifest: Path) -> None:
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            msg = f"invalid plugin.json: {exc}"
            logger.warning("Plugin %s skipped — %s", child.name, msg)
            self.errors.append({"path": str(child), "error": msg, "plugin": child.name})
            return
        except OSError as exc:
            msg = f"cannot read plugin.json: {exc}"
            logger.warning("Plugin %s skipped — %s", child.name, msg)
            self.errors.append({"path": str(child), "error": msg, "plugin": child.name})
            return

        try:
            cleaned = validate_manifest(
                meta if isinstance(meta, dict) else {}, folder_name=child.name
            )
        except ManifestError as exc:
            msg = str(exc)
            logger.warning("Plugin %s skipped — %s", child.name, msg)
            self.errors.append({"path": str(child), "error": msg, "plugin": child.name})
            return

        if not cleaned["enabled"]:
            logger.debug("Plugin %s disabled in manifest", child.name)
            return

        info: dict[str, Any] = {
            "id": cleaned["id"],
            "name": cleaned["name"],
            "version": cleaned["version"],
            "path": str(child),
            "description": cleaned.get("description") or "",
            "tags": list(cleaned.get("tags") or []),
            "tools": [],
        }

        tools = cleaned["tools"]
        registered = 0
        registered_names: list[str] = []
        modules_loaded: dict[str, Any] = {}

        for t in tools:
            name = t["name"]
            handler_name = t["handler"]
            mod_file = t["module"]
            mod_path = (child / mod_file).resolve()
            try:
                mod_path.relative_to(child.resolve())
            except ValueError:
                msg = f"module path escapes plugin dir: {mod_file}"
                logger.warning("Plugin %s: %s", info["id"], msg)
                self.errors.append(
                    {"path": str(child), "error": msg, "plugin": info["id"], "tool": name}
                )
                continue

            cache_key = str(mod_path)
            if cache_key not in modules_loaded:
                modules_loaded[cache_key] = self._load_module(mod_path, info["id"])
            mod = modules_loaded[cache_key]
            if mod is None:
                continue
            handler = getattr(mod, handler_name, None)
            if handler is None:
                logger.warning(
                    "Plugin %s: attribute %r not found in %s",
                    info["id"],
                    handler_name,
                    mod_path.name,
                )
                self.errors.append(
                    {
                        "path": str(mod_path),
                        "error": f"handler {handler_name!r} missing",
                        "plugin": info["id"],
                        "tool": name,
                    }
                )
                continue

            ok = self.registry.register(
                ToolSpec(
                    name=name,
                    description=t["description"],
                    handler=handler,
                    input_schema=t["input_schema"],
                    plugin=info["id"],
                    retries=int(t.get("retries", 2)),
                    tags=tuple(t.get("tags") or ()),
                )
            )
            if not ok:
                msg = f"tool name reserved by core: {name}"
                logger.warning("Plugin %s: %s", info["id"], msg)
                self.errors.append(
                    {"path": str(child), "error": msg, "plugin": info["id"], "tool": name}
                )
                continue
            registered += 1
            registered_names.append(name)

        if registered == 0 and tools:
            msg = "no tools registered (handlers failed or empty names)"
            logger.warning("Plugin %s: %s", info["id"], msg)
            self.errors.append({"path": str(child), "error": msg, "plugin": info["id"]})
            return

        # Optional lifecycle: on_load(registry_info) on primary module
        primary = child / "main.py"
        if primary.is_file():
            mod = modules_loaded.get(str(primary.resolve()))
            if mod is None:
                mod = self._load_module(primary.resolve(), info["id"])
            if mod is not None and callable(getattr(mod, "on_load", None)):
                try:
                    mod.on_load({"id": info["id"], "tools": list(registered_names)})
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Plugin %s on_load failed: %s", info["id"], exc)
                    self.errors.append(
                        {
                            "path": str(primary),
                            "error": f"on_load failed: {exc}",
                            "plugin": info["id"],
                        }
                    )

        info["tools"] = registered_names
        info["tool_count"] = registered
        self.loaded.append(info)
        logger.info(
            "Plugin loaded: %s v%s (%d tools)",
            info["id"],
            info["version"],
            registered,
        )

    def _load_module(self, path: Path, plugin_id: str) -> Any | None:
        import sys

        if not path.is_file():
            logger.warning("Plugin %s: module file missing: %s", plugin_id, path)
            self.errors.append(
                {"path": str(path), "error": "module file missing", "plugin": plugin_id}
            )
            return None
        # Exec source from disk (not stale bytecode after main.py edits)
        mod_name = f"gnom_plugin_{plugin_id}_{path.stem}_{next(_LOAD_SEQ)}"
        try:
            source = path.read_text(encoding="utf-8")
            code = compile(source, str(path), "exec")
            # Drop older gnom_plugin_<id>_* entries
            prefix = f"gnom_plugin_{plugin_id}_"
            for k in list(sys.modules):
                if k.startswith(prefix):
                    del sys.modules[k]
            mod = type(sys)("module")
            mod.__file__ = str(path)
            mod.__name__ = mod_name
            # provide common names plugins expect
            ns = {
                "__name__": mod_name,
                "__file__": str(path),
                "ToolSpec": ToolSpec,
                "registry": self.registry,
            }
            exec(code, ns, ns)  # noqa: S102
            # Drop plugin __pycache__ so next loads stay fresh
            try:
                import shutil

                pyc = path.parent / "__pycache__"
                if pyc.is_dir():
                    shutil.rmtree(pyc, ignore_errors=True)
            except Exception:  # noqa: BLE001
                pass
            try:
                importlib.invalidate_caches()
            except Exception:  # noqa: BLE001
                pass
            # Store as module-like
            for k, v in ns.items():
                setattr(mod, k, v)
            sys.modules[mod_name] = mod
            return mod
        except Exception as exc:
            logger.exception("Plugin %s load failed", plugin_id)
            self.errors.append({"path": str(path), "error": str(exc), "plugin": plugin_id})
            return None

    def _load_handler(self, path: Path, attr: str, plugin_id: str):
        mod = self._load_module(path, plugin_id)
        if mod is None:
            return None
        return getattr(mod, attr, None)
