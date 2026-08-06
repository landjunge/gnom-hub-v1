"""Configuration and key handling."""

from gnom_hub.config.keys import (
    ensure_env_from_key_txt,
    has_deepseek_key,
    load_keys,
    resolve_key_txt_path,
)
from gnom_hub.config.paths import (
    is_usb_root,
    personal_workspace,
    project_root,
    selected_dir,
    user_dir,
)
from gnom_hub.config.user_workspace import (
    backup_user_db,
    copy_selected_html,
    ensure_user_workspace,
    format_user_workspace_report,
    inspect_user_workspace,
)

__all__ = [
    "backup_user_db",
    "copy_selected_html",
    "ensure_env_from_key_txt",
    "ensure_user_workspace",
    "format_user_workspace_report",
    "has_deepseek_key",
    "inspect_user_workspace",
    "is_usb_root",
    "load_keys",
    "personal_workspace",
    "project_root",
    "resolve_key_txt_path",
    "selected_dir",
    "user_dir",
]
