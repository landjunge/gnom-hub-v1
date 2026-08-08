"""MCP-lite tool registry: name → callable + schema."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    input_schema: dict[str, Any] = field(default_factory=dict)
    plugin: str = "core"


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
            }
            for t in self._tools.values()
        ]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name].handler(**(arguments or {}))

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
