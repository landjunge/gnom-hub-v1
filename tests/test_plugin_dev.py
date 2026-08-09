"""Plugin development: manifest, sdk, lifecycle, reload, text_stats."""

from __future__ import annotations

from pathlib import Path

import pytest

from gnom_hub.config.paths import project_root
from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.manifest import ManifestError, validate_manifest
from gnom_hub.plugins.registry import ToolRegistry
from gnom_hub.plugins.retry import ToolRetry
from gnom_hub.plugins.sdk import fail, ok


def test_validate_manifest_ok():
    m = validate_manifest(
        {
            "id": "demo",
            "name": "Demo",
            "version": "1.0.0",
            "tags": ["util"],
            "tools": [
                {
                    "name": "demo_tool",
                    "description": "d",
                    "input_schema": {
                        "type": "object",
                        "properties": {"x": {"type": "string"}},
                        "required": ["x"],
                    },
                }
            ],
        },
        folder_name="demo",
    )
    assert m["id"] == "demo"
    assert m["tools"][0]["tags"] == ["util"]
    assert m["tools"][0]["handler"] == "run"


def test_validate_manifest_bad_name():
    with pytest.raises(ManifestError):
        validate_manifest(
            {"tools": [{"name": "bad name!"}]},
            folder_name="x",
        )


def test_sdk_ok_fail_retry():
    assert ok(a=1)["ok"] is True
    assert fail("nope")["ok"] is False
    with pytest.raises(ToolRetry):
        fail("tmp", retryable=True)


def test_echo_on_load_and_tags():
    reg = ToolRegistry()
    loader = PluginLoader(project_root() / "plugins", reg)
    loaded = loader.discover_and_load()
    echo = next(p for p in loaded if p["id"] == "echo")
    assert "echo" in echo["tools"]
    assert echo["version"] == "0.2.0"
    spec = reg.get("echo")
    assert spec is not None
    assert "demo" in (spec.tags or ())
    out = reg.call("echo", {"text": "hi"})
    assert out["ok"] is True
    assert out["echo"] == "hi"
    assert out["loads"] >= 1


def test_text_stats_plugin():
    reg = ToolRegistry()
    loader = PluginLoader(project_root() / "plugins", reg)
    loader.discover_and_load()
    out = reg.call("text_stats", {"text": "one two\nthree"})
    assert out["ok"] is True
    assert out["words"] == 3
    assert out["lines"] == 2


def test_reload_plugin(tmp_path: Path):
    # mini plugin tree
    root = tmp_path / "plugins" / "ping"
    root.mkdir(parents=True)
    (root / "plugin.json").write_text(
        """{
      "id": "ping",
      "name": "Ping",
      "version": "0.1.0",
      "enabled": true,
      "tools": [{"name": "ping", "description": "p", "module": "main.py", "handler": "run"}]
    }""",
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "def run():\n    return {'pong': 1}\n",
        encoding="utf-8",
    )
    reg = ToolRegistry()
    loader = PluginLoader(tmp_path / "plugins", reg)
    loader.discover_and_load()
    assert reg.call("ping") == {"pong": 1}
    (root / "main.py").write_text(
        "def run():\n    return {'pong': 2}\n",
        encoding="utf-8",
    )
    r = loader.reload("ping")
    assert r["ok"] is True
    assert reg.call("ping") == {"pong": 2}


def test_template_folder_not_loaded():
    reg = ToolRegistry()
    loader = PluginLoader(project_root() / "plugins", reg)
    loaded = loader.discover_and_load()
    assert not any(p["id"] == "my_plugin" for p in loaded)
    assert not any(p["id"] == "_template" for p in loaded)
