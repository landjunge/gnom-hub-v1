---
id: tool_honesty
name: Tool honesty
version: 0.1.0
enabled: true
description: Never invent tool results; use TOOL_CALL protocol
tags: [tools, honesty]
agents: [worker1, worker2, worker3, worker4, coordinator]
triggers: [tool_drill, browser_nav, tool, playwright, shell]
---

# Tool honesty

- Only report tool outcomes that actually returned via `TOOL_RESULT`.
- Missing dependency → call ensure/install tool or state dry-run — do not fake success.
- Live browser ≠ HTML file generation.
- God-Mode off → shell/GUI may be dry-run; say so.
