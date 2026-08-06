"""Configuration and key handling."""

from gnom_hub.config.keys import (
    ensure_env_from_key_txt,
    has_deepseek_key,
    load_keys,
    resolve_key_txt_path,
)
from gnom_hub.config.paths import project_root, user_dir
from gnom_hub.config.user_workspace import (
    ensure_user_workspace,
    format_user_workspace_report,
    inspect_user_workspace,
)

__all__ = [
    "ensure_env_from_key_txt",
    "ensure_user_workspace",
    "format_user_workspace_report",
    "has_deepseek_key",
    "inspect_user_workspace",
    "load_keys",
    "project_root",
    "resolve_key_txt_path",
    "user_dir",
]
