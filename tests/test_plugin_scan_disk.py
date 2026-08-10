"""Plugin drop-in disk inventory (scan_disk)."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry


def test_scan_disk_lists_bundled_plugins(tmp_path: Path):
    # Use real plugins dir if present; else minimal fixture
    repo_plugins = Path(__file__).resolve().parents[1] / "plugins"
    if repo_plugins.is_dir():
        reg = ToolRegistry()
        loader = PluginLoader(repo_plugins, reg)
        loader.discover_and_load()
        disk = loader.scan_disk()
        assert isinstance(disk, list)
        assert disk, "expected at least one plugin folder"
        ids = {d.get("id") or d.get("folder") for d in disk}
        # bundled echo plugin should be visible
        assert "echo" in ids or any("echo" in str(x) for x in ids)
        loaded = [d for d in disk if d.get("status") == "loaded"]
        assert loaded, "expected at least one loaded plugin after discover"
    else:
        plug = tmp_path / "demo"
        plug.mkdir()
        (plug / "plugin.json").write_text(
            '{"id":"demo","name":"Demo","version":"0.1.0","enabled":true,"tools":[]}',
            encoding="utf-8",
        )
        reg = ToolRegistry()
        loader = PluginLoader(tmp_path, reg)
        loader.discover_and_load()
        disk = loader.scan_disk()
        assert len(disk) == 1
        assert disk[0]["id"] == "demo"
        assert disk[0]["status"] in ("loaded", "not_loaded", "disabled")


def test_scan_disk_marks_disabled(tmp_path: Path):
    plug = tmp_path / "off"
    plug.mkdir()
    (plug / "plugin.json").write_text(
        '{"id":"off","name":"Off","version":"0.1.0","enabled":false,"tools":[]}',
        encoding="utf-8",
    )
    reg = ToolRegistry()
    loader = PluginLoader(tmp_path, reg)
    loader.discover_and_load()
    disk = loader.scan_disk()
    assert disk[0]["status"] == "disabled"
    assert disk[0]["enabled"] is False


def test_scan_disk_no_manifest(tmp_path: Path):
    (tmp_path / "empty_folder").mkdir()
    reg = ToolRegistry()
    loader = PluginLoader(tmp_path, reg)
    disk = loader.scan_disk()
    assert disk[0]["status"] == "no_manifest"
