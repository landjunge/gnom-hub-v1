"""MCP-lite tool registry: name → callable + schema."""

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

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "plugin": t.plugin,
                "retries": t.retries,
            }
            for t in self._tools.values()
        ]

    def call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        retries: int | None = None,
    ) -> Any:
        """Call a tool; honor ToolRetry up to budget, then raise ToolFailed.

        ``retries`` overrides the per-tool default from ToolSpec (default 2).
        KeyError if unknown. ToolFailed is terminal. Other exceptions propagate.
        """
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        spec = self._tools[name]
        budget = spec.retries if retries is None else retries
        try:
            return call_with_retry(
                spec.handler,
                arguments,
                retries=budget,
                tool_name=name,
            )
        except ToolFailed:
            raise
        except ToolRetry as exc:
            # call_with_retry should already convert; keep defensive
            raise ToolFailed(str(exc.message or exc)) from exc

    def mcp_manifest(self) -> dict[str, Any]:
        """Minimal MCP-style tools/list payload."""
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema or {"type": "object", "properties": {}},
                }
                for t in self._tools.values()
            ]
        }
