#!/usr/bin/env python3
"""GitHub pull_request webhook: start Builder on changes_requested."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_STATE = Path("data/webhook_started.json")
BUILDER_PROMPT = Path("agents/builder.md")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(action: str, pr: int | None = None, detail: str = "") -> None:
    parts = [utc_now(), action]
    if pr is not None:
        parts.append(f"pr=#{pr}")
    if detail:
        parts.append(detail)
    print(" ".join(parts), flush=True)


def webhook_secret() -> str:
    return (os.environ.get("GNOM_WEBHOOK_SECRET") or "").strip()


def builder_cmd() -> str:
    return (os.environ.get("GNOM_BUILDER_CMD") or "").strip()


def sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not secret or not header:
        return False
    expected = sign_body(secret, body)
    return hmac.compare_digest(expected, header.strip())


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"started": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"started": {}}
    started = raw.get("started") if isinstance(raw, dict) else {}
    if not isinstance(started, dict):
        started = {}
    return {"started": {str(k): v for k, v in started.items()}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def builder_prompt(pr_number: int, prompt_path: Path = BUILDER_PROMPT) -> str:
    text = ""
    if prompt_path.is_file():
        text = prompt_path.read_text(encoding="utf-8").strip()
    hint = f"arbeite die Review-Kommentare zu PR #{pr_number} ab"
    if text:
        return f"{text}\n\n{hint}\n"
    return hint + "\n"


def launch_builder(pr_number: int, prompt: str, cmd: str | None = None) -> str:
    raw = (cmd if cmd is not None else builder_cmd()).strip()
    argv = shlex.split(raw)
    if not argv:
        raise RuntimeError("missing-builder-cmd")
    env = os.environ.copy()
    env["PR_NUMBER"] = str(pr_number)
    env["ISSUE_NUMBER"] = str(pr_number)
    subprocess.run(argv, check=True, input=prompt, text=True, env=env)
    return f"cmd:{argv[0]}"


def pr_number_from(payload: dict[str, Any]) -> int | None:
    pr = payload.get("pull_request")
    if isinstance(pr, dict) and pr.get("number") is not None:
        try:
            return int(pr["number"])
        except (TypeError, ValueError):
            return None
    if payload.get("number") is not None:
        try:
            return int(payload["number"])
        except (TypeError, ValueError):
            return None
    return None


def is_changes_requested(event: str, payload: dict[str, Any]) -> bool:
    action = str(payload.get("action") or "")
    if event == "pull_request" and action == "changes_requested":
        return True
    if event == "pull_request_review":
        review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
        state = str(review.get("state") or "").lower()
        return action == "submitted" and state == "changes_requested"
    return False


def handle_event(
    *,
    event: str,
    payload: dict[str, Any],
    state_path: Path,
    prompt_path: Path = BUILDER_PROMPT,
    cmd: str | None = None,
    launch: Any = launch_builder,
) -> dict[str, Any]:
    number = pr_number_from(payload)
    action = str(payload.get("action") or "")
    if event == "pull_request" and action in ("opened", "synchronize"):
        log("ignore", number, action)
        return {"status": "ignored", "reason": action, "pr": number}
    if not is_changes_requested(event, payload):
        log("ignore", number, action or event or "unknown")
        return {"status": "ignored", "reason": action or event, "pr": number}
    if number is None:
        log("error", detail="missing-pr-number")
        return {"status": "error", "reason": "missing-pr-number"}
    state = load_state(state_path)
    if str(number) in (state.get("started") or {}):
        log("skip-already-started", number)
        return {"status": "skipped", "reason": "already-started", "pr": number}
    raw_cmd = builder_cmd() if cmd is None else cmd
    if not raw_cmd:
        log("error", number, "missing-builder-cmd")
        return {"status": "error", "reason": "missing-builder-cmd", "pr": number}
    prompt = builder_prompt(number, prompt_path)
    how = launch(number, prompt, raw_cmd)
    state.setdefault("started", {})[str(number)] = {"at": utc_now(), "how": how}
    save_state(state_path, state)
    log("start-builder", number, how)
    return {"status": "started", "pr": number, "how": how}


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "gnom-pr-webhook/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/health", "/"):
            self._send(200, {"ok": True})
            return
        self._send(404, {"ok": False, "error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/webhook":
            self._send(404, {"ok": False, "error": "not-found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b"{}"
        secret = webhook_secret()
        if not secret:
            log("error", detail="missing-webhook-secret")
            self._send(503, {"ok": False, "error": "missing-webhook-secret"})
            return
        header = self.headers.get("X-Hub-Signature-256")
        if not header:
            log("reject", detail="missing-signature")
            self._send(401, {"ok": False, "error": "missing-signature"})
            return
        if not verify_signature(secret, body, header):
            log("reject", detail="bad-signature")
            self._send(401, {"ok": False, "error": "bad-signature"})
            return
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "invalid-json"})
            return
        if not isinstance(payload, dict):
            self._send(400, {"ok": False, "error": "invalid-json"})
            return
        event = self.headers.get("X-GitHub-Event") or ""
        result = handle_event(
            event=event,
            payload=payload,
            state_path=self.server.state_path,  # type: ignore[attr-defined]
            prompt_path=self.server.prompt_path,  # type: ignore[attr-defined]
        )
        code = 200
        if result.get("status") == "error":
            code = 503 if result.get("reason") == "missing-builder-cmd" else 400
        self._send(code, {"ok": result.get("status") != "error", **result})


def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    state_path: Path = DEFAULT_STATE,
    prompt_path: Path = BUILDER_PROMPT,
) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), WebhookHandler)
    httpd.state_path = state_path  # type: ignore[attr-defined]
    httpd.prompt_path = prompt_path  # type: ignore[attr-defined]
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--prompt", type=Path, default=BUILDER_PROMPT)
    args = parser.parse_args(argv)
    if not webhook_secret():
        log("error", detail="missing-webhook-secret set GNOM_WEBHOOK_SECRET")
        return 2
    httpd = serve(args.host, args.port, args.state, args.prompt)
    log("listen", detail=f"{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("stop")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
