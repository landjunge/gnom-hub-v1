# Plugin template

1. Copy to `plugins/<your_id>/` (no leading `_`)
2. Edit `plugin.json` (`id`, tool `name`, schema)
3. Implement `run` in `main.py`
4. Restart hub (or `POST /api/plugins/reload`)

Helpers: `from gnom_hub.plugins.sdk import ok, fail, retry, ToolFailed, ToolRetry`
