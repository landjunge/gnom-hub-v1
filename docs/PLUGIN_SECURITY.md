# Plugins — loading, authoring & security

## How load works

1. Scan `plugins/<name>/plugin.json` (skip `_template` / `.*`)
2. Validate manifest (`src/gnom_hub/plugins/manifest.py`)
3. Import `main.py` (or declared `module`) via `importlib.exec_module`
4. Bind handler into `ToolRegistry` (tags, retries from JSON)
5. Optional `on_load(info)` lifecycle on `main.py`

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

## Authoring

```bash
python scripts/new_plugin.py my_tool
# → plugins/my_tool/ from plugins/_template
```

Minimal `main.py`:

```python
from gnom_hub.plugins.sdk import ok, fail, retry, ToolRetry, ToolFailed

def on_load(info: dict) -> None:
    ...

def run(text: str = "") -> dict:
    if not text:
        return fail("text required")
    return ok(result=text)
```

Manifest fields: `id`, `name`, `version`, `enabled`, `description`, `tags[]`, `tools[]`  
Per tool: `name`, `description`, `module`, `handler`, `input_schema`, `retries`, `tags[]`

Dev reload: `POST /api/plugins/reload?plugin_id=echo`

## Failures

| Case | Behavior |
|------|----------|
| Invalid JSON / manifest | warning + `GET /api/plugins` → `errors` |
| exec/import error | `logger.exception` + `errors`; plugin skipped |
| missing handler | warning; tool not registered |
| core name clash | refused (M5) |

Code: `loader.py`, `manifest.py`, `sdk.py`, `registry.py`
