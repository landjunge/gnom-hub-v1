"""Never open Kleinanzeigen unless the user explicitly navigates there."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.tools.agent_bridge import is_live_browser_task, resolve_browser_url
from gnom_hub.tools.browser_tools import extract_urls
from gnom_hub.tools.tool_scenarios import LIVE_SITE


def test_empty_extract_urls_not_kleinanzeigen():
    assert extract_urls("") == []
    assert extract_urls("hello") == []
    assert extract_urls("kleinanzeigen") == []


def test_bare_name_does_not_auto_navigate():
    assert resolve_browser_url("") == ""
    assert resolve_browser_url("kleinanzeigen") == ""
    assert not is_live_browser_task("kleinanzeigen")
    assert not is_live_browser_task("kleinanzeigen.de")
    assert "kleinanzeigen" in resolve_browser_url("öffne kleinanzeigen")


def test_pw_goto_source_has_no_default_marketplace():
    src = Path("plugins/playwright_browser/main.py").read_text(encoding="utf-8")
    assert "kleinanzeigen" not in src.lower()
    assert "url required" in src


def test_drill_live_site_is_example_org():
    assert "kleinanzeigen" not in LIVE_SITE.lower()
    assert "example.org" in LIVE_SITE
