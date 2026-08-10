"""MCP-lite tool registry: name → callable + schema + light validation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from gnom_hub.plugins.retry import ToolFailed, ToolRetry, call_with_retry


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    input_schema: dict[str, Any] = field(default_factory=dict)
    plugin: str = "core"
    # Extra attempts after first call when handler raises ToolRetry
    retries: int = 2
    # Optional grouping: e.g. ("hub", "memory", "workspace")
    tags: tuple[str, ...] = ()


def _validate_arguments(spec: ToolSpec, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Enforce required keys from a minimal JSON-schema-like input_schema."""
    args = dict(arguments or {})
    schema = spec.input_schema or {}
    required = schema.get("required") or []
    if not isinstance(required, list):
        return args
    missing = [str(k) for k in required if k not in args or args.get(k) in (None, "")]
    if missing:
        raise ToolFailed(f"tool {spec.name!r}: missing required arg(s): {', '.join(missing)}")
    props = schema.get("properties")
    if isinstance(props, dict) and props:
        # drop unknown keys only when schema is explicit (keep extras if no properties)
        known = set(props.keys())
        # do not strip — agents may pass optional extras; just type-hint ints when declared
        for key, meta in props.items():
            if key not in args or not isinstance(meta, dict):
                continue
            want = meta.get("type")
            if want == "integer" and isinstance(args[key], str) and str(args[key]).isdigit():
                args[key] = int(args[key])
            elif want == "boolean" and isinstance(args[key], str):
                low = args[key].strip().lower()
                if low in ("1", "true", "yes", "on"):
                    args[key] = True
                elif low in ("0", "false", "no", "off"):
                    args[key] = False
            _ = known  # reserved for future strict mode
    return args


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec, *, overwrite: bool = False) -> bool:
        """
        Register a tool. Returns False if registration was refused (M5).

        Core tools cannot be overwritten by plugins unless overwrite=True.
        """
        existing = self._tools.get(spec.name)
        if (
            existing is not None
            and existing.plugin == "core"
            and (spec.plugin or "") != "core"
            and not overwrite
        ):
            return False
        self._tools[spec.name] = spec
        return True

    def unregister(self, name: str, *, force: bool = False) -> bool:
        """Remove a tool. Core tools require force=True."""
        spec = self._tools.get(name)
        if spec is None:
            return False
        if spec.plugin == "core" and not force:
            return False
        del self._tools[name]
        return True

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def list_tools(self, *, tag: str | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for t in self._tools.values():
            if tag and tag not in (t.tags or ()):
                continue
            out.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                    "plugin": t.plugin,
                    "retries": t.retries,
                    "tags": list(t.tags or ()),
                }
            )
        out.sort(key=lambda x: x["name"])
        return out

    def call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        retries: int | None = None,
    ) -> Any:
        """Call a tool; honor ToolRetry up to budget, then raise ToolFailed.

        ``retries`` overrides the per-tool default from ToolSpec (default 2).
        KeyError if unknown. Unexpected handler errors become ToolFailed (terminal).
        """
        if name not in self._tools:
            known = ", ".join(self.names()) or "(none)"
            raise KeyError(f"Unknown tool: {name}. Available: {known}")
        spec = self._tools[name]
        args = _validate_arguments(spec, arguments)
        budget = spec.retries if retries is None else retries
        try:
            return call_with_retry(
                spec.handler,
                args,
                retries=budget,
                tool_name=name,
            )
        except ToolFailed:
            raise
        except ToolRetry as exc:
            raise ToolFailed(
                str(exc.message or exc),
                code="tool_failed",
                retryable=False,
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ToolFailed(
                f"tool {name!r}: {exc}",
                code="validation",
                retryable=False,
            ) from exc
        except Exception as exc:
            raise ToolFailed(
                f"tool {name!r}: {type(exc).__name__}: {exc}",
                code="internal",
                retryable=False,
            ) from exc

    def mcp_manifest(self) -> dict[str, Any]:
        """Minimal MCP-style tools/list payload."""
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema or {"type": "object", "properties": {}},
                }
                for t in sorted(self._tools.values(), key=lambda x: x.name)
            ]
        }
