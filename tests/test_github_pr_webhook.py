"""GitHub pull_request webhook — signature and action gates, no live GitHub."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import sys
import threading
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "github_pr_webhook.py"


def _load():
    name = "gnom_github_pr_webhook"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


wh = _load()
SECRET = "test-secret"
OK_CMD = f"{sys.executable} -c pass"


def _sig(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _pr_payload(number: int, action: str) -> dict:
    return {"action": action, "number": number, "pull_request": {"number": number}}


def test_valid_signature_accepts():
    body = b'{"action":"opened"}'
    assert wh.verify_signature(SECRET, body, _sig(body)) is True


def test_invalid_signature_rejects():
    body = b'{"action":"opened"}'
    assert wh.verify_signature(SECRET, body, "sha256=deadbeef") is False


def test_missing_header_rejects():
    body = b'{"action":"opened"}'
    assert wh.verify_signature(SECRET, body, None) is False
    assert wh.verify_signature(SECRET, body, "") is False


def test_wrong_action_is_ignored(tmp_path: Path):
    out = wh.handle_event(
        event="pull_request",
        payload=_pr_payload(109, "labeled"),
        state_path=tmp_path / "state.json",
        cmd=OK_CMD,
    )
    assert out["status"] == "ignored"
    assert not (tmp_path / "state.json").exists()


def test_opened_and_synchronize_do_not_start(tmp_path: Path):
    for action in ("opened", "synchronize"):
        out = wh.handle_event(
            event="pull_request",
            payload=_pr_payload(107, action),
            state_path=tmp_path / "state.json",
            cmd=OK_CMD,
        )
        assert out["status"] == "ignored"
        assert out["reason"] == action
    assert not (tmp_path / "state.json").exists()


def test_changes_requested_starts_once(tmp_path: Path):
    launched: list[int] = []

    def launch(number, prompt, cmd):
        launched.append(number)
        assert "PR #109" in prompt
        assert "Review-Kommentare" in prompt
        return "cmd:ok"

    first = wh.handle_event(
        event="pull_request",
        payload=_pr_payload(109, "changes_requested"),
        state_path=tmp_path / "state.json",
        cmd=OK_CMD,
        launch=launch,
    )
    assert first["status"] == "started"
    second = wh.handle_event(
        event="pull_request",
        payload=_pr_payload(109, "changes_requested"),
        state_path=tmp_path / "state.json",
        cmd=OK_CMD,
        launch=launch,
    )
    assert second["status"] == "skipped"
    assert launched == [109]


def test_http_missing_signature_header(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GNOM_WEBHOOK_SECRET", SECRET)
    httpd = wh.serve("127.0.0.1", 0, tmp_path / "state.json", tmp_path / "p.md")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        conn = HTTPConnection(host, port, timeout=5)
        body = json.dumps(_pr_payload(1, "opened")).encode()
        conn.request("POST", "/webhook", body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 401
        data = json.loads(resp.read().decode())
        assert data["error"] == "missing-signature"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_invalid_signature(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GNOM_WEBHOOK_SECRET", SECRET)
    httpd = wh.serve("127.0.0.1", 0, tmp_path / "state.json", tmp_path / "p.md")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        conn = HTTPConnection(host, port, timeout=5)
        body = json.dumps(_pr_payload(1, "opened")).encode()
        conn.request(
            "POST",
            "/webhook",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=00",
                "X-GitHub-Event": "pull_request",
            },
        )
        resp = conn.getresponse()
        assert resp.status == 401
        data = json.loads(resp.read().decode())
        assert data["error"] == "bad-signature"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_valid_signature_wrong_action(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GNOM_WEBHOOK_SECRET", SECRET)
    httpd = wh.serve("127.0.0.1", 0, tmp_path / "state.json", tmp_path / "p.md")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address[:2]
        conn = HTTPConnection(host, port, timeout=5)
        body = json.dumps(_pr_payload(58, "opened")).encode()
        conn.request(
            "POST",
            "/webhook",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sig(body),
                "X-GitHub-Event": "pull_request",
            },
        )
        resp = conn.getresponse()
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["status"] == "ignored"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_shell_true_not_used():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "shell=True" not in src


def test_main_missing_secret_exits_2(monkeypatch):
    monkeypatch.delenv("GNOM_WEBHOOK_SECRET", raising=False)
    assert wh.main(["--port", "8099"]) == 2
