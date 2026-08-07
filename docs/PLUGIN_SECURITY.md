# Plugins — loading & security

## How load works

1. Scan `plugins/<name>/plugin.json`
2. For each tool: import `main.py` (or declared `module`) via `importlib.exec_module`
3. Bind handler attribute (default `run`) into `ToolRegistry`

## Trust model

**Local desk only.** Plugin code runs with the **same privileges as the hub process**.

At import time a plugin can:

- read/write files the hub user can access  
- open network connections  
- import any installed package  

God-Mode / computer-use are **separate** gates; plugins do not automatically get mouse/shell.

### Rules

| Do | Don’t |
|----|--------|
| Only install plugins you trust / wrote yourself | Drop random zip packs from the internet into `plugins/` |
| Review `main.py` before first load | Treat plugins as a sandboxed app store |
| Keep `enabled: false` while testing | Expect path-escape protection alone to stop malware |

Path escape of `module` outside the plugin folder is rejected by the loader.

## Failures (since loader harden)

| Case | Behavior |
|------|----------|
| Invalid JSON | warning log + listed in `GET /api/plugins` → `errors` |
| exec/import error | `logger.exception` + `errors` entry; plugin skipped |
| missing handler | warning; tool not registered |

## Optional later

- JSON Schema / pydantic for manifests  
- Optional subprocess sandbox for untrusted packs (out of V1 scope)

Code: `src/gnom_hub/plugins/loader.py`
