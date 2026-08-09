"""plugin.json validation (light, no external schema lib)."""

from __future__ import annotations

from typing import Any


class ManifestError(ValueError):
    """Invalid plugin manifest."""


def validate_manifest(meta: dict[str, Any], *, folder_name: str) -> dict[str, Any]:
    """
    Normalize + validate a plugin.json object.

    Returns a cleaned dict with keys: id, name, version, enabled, description,
    tags, tools (list of tool defs).
    Raises ManifestError on hard failures.
    """
    if not isinstance(meta, dict):
        raise ManifestError("plugin.json root must be an object")

    pid = str(meta.get("id") or folder_name).strip()
    if not pid or "/" in pid or "\\" in pid or pid in (".", ".."):
        raise ManifestError("invalid plugin id")

    name = str(meta.get("name") or pid).strip() or pid
    version = str(meta.get("version") or "0.0.0").strip() or "0.0.0"
    enabled = meta.get("enabled")
    if enabled is None:
        enabled = True
    if not isinstance(enabled, bool):
        raise ManifestError("enabled must be a boolean when set")

    description = str(meta.get("description") or "").strip()
    tags = _as_str_list(meta.get("tags"), field="tags")

    tools_raw = meta.get("tools")
    if tools_raw is None:
        tools_raw = []
    if not isinstance(tools_raw, list):
        raise ManifestError("tools must be a list")

    tools: list[dict[str, Any]] = []
    for i, t in enumerate(tools_raw):
        if not isinstance(t, dict):
            raise ManifestError(f"tools[{i}] must be an object")
        tname = t.get("name")
        if not tname or not isinstance(tname, str) or not tname.strip():
            raise ManifestError(f"tools[{i}].name must be a non-empty string")
        tname = tname.strip()
        if not tname.replace("_", "").replace("-", "").isalnum():
            raise ManifestError(f"tools[{i}].name has invalid characters: {tname!r}")

        handler = str(t.get("handler") or "run").strip() or "run"
        module = str(t.get("module") or "main.py").strip() or "main.py"
        if ".." in module.replace("\\", "/").split("/"):
            raise ManifestError(f"tools[{i}].module must not contain ..")

        schema = t.get("input_schema") or {}
        if not isinstance(schema, dict):
            raise ManifestError(f"tools[{i}].input_schema must be an object")

        retries = t.get("retries", 2)
        try:
            retries_i = int(retries)
        except (TypeError, ValueError) as exc:
            raise ManifestError(f"tools[{i}].retries must be int") from exc
        if retries_i < 0 or retries_i > 8:
            raise ManifestError(f"tools[{i}].retries out of range 0–8")

        tool_tags = _as_str_list(t.get("tags"), field=f"tools[{i}].tags")
        # inherit plugin tags
        for tg in tags:
            if tg not in tool_tags:
                tool_tags.append(tg)

        tools.append(
            {
                "name": tname,
                "description": str(t.get("description") or tname),
                "module": module,
                "handler": handler,
                "input_schema": schema,
                "retries": retries_i,
                "tags": tool_tags,
            }
        )

    return {
        "id": pid,
        "name": name,
        "version": version,
        "enabled": bool(enabled),
        "description": description,
        "tags": tags,
        "tools": tools,
    }


def _as_str_list(raw: Any, *, field: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ManifestError(f"{field} must be a list of strings")
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if s and s not in out:
            out.append(s)
    return out
