"""Tests for safe web_fetch tool."""

from __future__ import annotations

import importlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

# tools/__init__ exports `web_fetch` function — must load submodule by name
wf = importlib.import_module("gnom_hub.tools.web_fetch")
web_fetch = wf.web_fetch


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


def test_web_fetch_blocks_redirect_to_private():
    """A hop that 302s to 127.0.0.1 must be rejected (SSRF)."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/secret")
            self.end_headers()

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    orig = wf._is_private_host
    try:
        hop = {"n": 0}

        def _mock_private(host: str) -> bool:
            # Treat first request host as public so we can hit the redirect hop.
            hop["n"] += 1
            if hop["n"] == 1 and host in ("127.0.0.1", "localhost"):
                return False
            return orig(host)

        wf._is_private_host = _mock_private  # type: ignore[assignment]
        r = wf.web_fetch(f"http://127.0.0.1:{port}/", timeout=3.0)
        assert r["ok"] is False
        err = (r.get("error") or "").lower()
        assert any(x in err for x in ("private", "local", "redirect", "403", "blocked"))
    finally:
        wf._is_private_host = orig  # type: ignore[assignment]
        server.shutdown()


def test_prefetch_urls_empty():
    from gnom_hub.pipeline.orchestrator import _prefetch_urls

    assert _prefetch_urls("no links here") == ""
