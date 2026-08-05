"""Tests for safe web_fetch tool."""

from gnom_hub.tools.web_fetch import web_fetch


def test_web_fetch_rejects_empty():
    r = web_fetch("")
    assert r["ok"] is False


def test_web_fetch_rejects_non_http():
    r = web_fetch("ftp://example.com/x")
    assert r["ok"] is False


def test_web_fetch_blocks_localhost():
    r = web_fetch("http://127.0.0.1/")
    assert r["ok"] is False
    assert "private" in r.get("error", "").lower() or "local" in r.get("error", "").lower()
