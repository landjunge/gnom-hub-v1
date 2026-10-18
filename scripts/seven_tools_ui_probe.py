#!/usr/bin/env python3
"""Headed, deterministic UI/API probe. No Hub/model/credential/runtime is loaded.

Serves actual source HTML/JS/CSS with synthetic API fixtures on a random loopback
port. Uses the existing real-Chrome fallback pattern in real_user_quality_e2e.
No existing user tab or service is connected, navigated, changed or stopped.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/gnom_hub/ui/static"
OUT = ROOT / "docs/evidence/seven-tools-20261018"


class Fixture:
    lang = "de"
    controlled = False
    phase = "brainstorm"
    execute_calls = 0
    poll_calls = 0
    answer_calls = 0
    requests: ClassVar[list[str]] = []
    unexpected_posts: ClassVar[list[str]] = []

    @classmethod
    def providers(cls):
        return {
            "execution_profile": "controlled" if cls.controlled else "standalone",
            "controlled_execution_ready": False,
        }

    @classmethod
    def system(cls):
        note = (
            "Controlled execution blocked: workflow, provider and protected access are not connected."
            if cls.lang == "en"
            else "Kontrollierte Ausführung gesperrt: Auftrags-, Provider- und Zugangsanbindung fehlen."
        )
        return {
            "ui_lang": cls.lang,
            "providers": cls.providers(),
            "version": "3.10.1",
            "auto_backup_before_execute": False,
            "deepseek": False,
            "ollama": False,
            "setup": {
                "key_ok": False,
                "tollgate_ok": False,
                "tollgate_note": "Synthetic fixture: no provider connected",
                "controlled_execution_note": note if cls.controlled else "",
            },
            "backups": [],
            "packs": [],
        }

    @classmethod
    def agents(cls):
        return [
            {
                "id": key,
                "name": key.title(),
                "enabled": True,
                "toggleable": False,
                "color": "#afb6c1",
            }
            for key in ("brainstorm", "coordinator", "flex", "memory", "worker1", "worker2")
        ]

    @classmethod
    def snapshot(cls):
        question = {
            "question_id": "synthetic-q1",
            "job_id": "synthetic-question",
            "task_id": "synthetic-task",
            "agent_id": "coordinator",
            "component": "single_select",
            "status": "open",
            "text": (
                "SYNTHETIC UI TEST — Continue the harmless dummy review? No model, account, provider or real workflow is involved. This question is deliberately long to check readable wrapping."
                if cls.lang == "en"
                else "SYNTHETISCHER UI-TEST — Soll die ungefährliche Dummy-Prüfung fortgesetzt werden? Kein Modell, Konto, Provider oder echter Auftrag ist beteiligt. Die lange Frage prüft den lesbaren Zeilenumbruch."
            ),
            "options": ["Continue dummy review", "Stop demo"]
            if cls.lang == "en"
            else ["Dummy-Prüfung fortsetzen", "Demo stoppen"],
        }
        result = "SYNTHETIC UI DELIVERY — UNVERIFIED / SYNTHETISCHE UI-LIEFERUNG — UNGEPRÜFT"
        return {
            "version": "3.10.1",
            "agents": cls.agents(),
            "ui_lang": cls.lang,
            "llm": {"deepseek": False, "ollama": False, "providers": cls.providers(), "auth": {}},
            "tollgate": {"ready": False, "error": "synthetic fixture; no provider"},
            "god_mode": {"enabled": False},
            "memory": {},
            "workspace": {},
            "pipeline": {
                "stage": "clarify"
                if cls.phase == "question"
                else "done"
                if cls.phase == "answer"
                else "brainstorm",
                "user_text": "Synthetic UI-only task",
                "can_execute": True,
                "messages": [{"role": "user", "visible_text": "Synthetic UI-only task"}],
                "worker_outputs": [{"worker": "worker1", "result": result}]
                if cls.phase == "answer"
                else [],
                "result_status": "UNVERIFIED",
            },
            "flex_box1": {"questions": [question] if cls.phase == "question" else []},
        }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, value, status=200):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlsplit(self.path).path
        Fixture.requests.append("GET " + path)
        if path == "/api/state":
            return self.reply(Fixture.snapshot())
        if path == "/api/agents":
            return self.reply({"agents": Fixture.agents()})
        if path == "/api/system":
            return self.reply(Fixture.system())
        if path.startswith("/api/jobs/synthetic-"):
            Fixture.poll_calls += 1
            return self.reply(
                {
                    "status": "clarify" if Fixture.phase == "question" else "done",
                    "finished": True,
                    "snapshot": Fixture.snapshot(),
                }
            )
        if path == "/api/jobs/busy":
            return self.reply({"busy": False})
        if path == "/api/tool-targets":
            return self.reply({"tools": []})
        if path == "/api/tooltips":
            return self.reply({"tooltips": {}})
        if path.startswith("/api/"):
            return self.reply({})
        target = STATIC / (
            "v4.html"
            if path == "/v4"
            else "index.html"
            if path == "/"
            else path.removeprefix("/static/").lstrip("/")
        )
        target = target.resolve()
        if not target.is_relative_to(STATIC) or not target.is_file():
            return self.reply({"error": "fixture_not_found"}, 404)
        raw = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            {
                ".html": "text/html",
                ".js": "application/javascript",
                ".css": "text/css",
                ".svg": "image/svg+xml",
            }.get(target.suffix, "application/octet-stream"),
        )
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        path = urlsplit(self.path).path
        Fixture.requests.append("POST " + path)
        length = int(self.headers.get("Content-Length", 0))
        if length > 4096:
            return self.reply({"error": "fixture_body_limit"}, 413)
        body = json.loads(self.rfile.read(length) or b"{}")
        if path == "/api/agents/enable-all":
            # Existing legacy bootstrap; synthetic fixture agents already on.
            return self.reply({"agents": Fixture.agents()})
        if path == "/api/execute":
            if Fixture.controlled:
                return self.reply({"detail": {"message": "controlled_execution_unavailable"}}, 403)
            Fixture.execute_calls += 1
            Fixture.phase = "question"
            return self.reply({"job_id": "synthetic-question", "status": "running"})
        if path == "/api/flex/answer":
            assert body["question_id"] == "synthetic-q1" and body["job_id"] == "synthetic-question"
            Fixture.answer_calls += 1
            Fixture.phase = "answer"
            return self.reply({"job_id": "synthetic-answer", "status": "running"})
        Fixture.unexpected_posts.append(path)
        return self.reply({"detail": {"message": "fixture_action_not_allowed"}}, 403)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    errors, cases = [], []
    try:
        with sync_playwright() as playwright:
            # Existing harness explicitly falls back to real Chrome channel when
            # configured CDP9222 is unavailable. Temporary profile, headed only.
            browser = playwright.chromium.launch(channel="chrome", headless=False, slow_mo=50)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                reduced_motion="reduce",
                service_workers="block",
            )
            context.route(
                "**/*",
                lambda route: (
                    route.continue_() if route.request.url.startswith(base + "/") else route.abort()
                ),
            )
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            try:
                for lang in ("de", "en"):
                    Fixture.lang, Fixture.controlled, Fixture.phase = lang, False, "brainstorm"
                    before = (Fixture.execute_calls, Fixture.poll_calls, Fixture.answer_calls)
                    page.goto(base + "/v4")
                    page.locator("#execute").click()
                    question = page.locator(".decision-card")
                    expect(question).to_contain_text(
                        "SYNTHETIC" if lang == "en" else "SYNTHETISCHER"
                    )
                    button = question.get_by_role("button").first
                    expect(button).to_be_enabled(timeout=10000)
                    button.focus()
                    page.keyboard.press("Tab")
                    page.keyboard.press("Shift+Tab")
                    button.scroll_into_view_if_needed()
                    assert button.evaluate("el => el.scrollWidth <= el.clientWidth")
                    assert button.evaluate("el => getComputedStyle(el).whiteSpace") == "normal"
                    assert question.evaluate(
                        "el => el.clientWidth > el.parentElement.clientWidth * 0.8"
                    )
                    page.screenshot(path=str(OUT / f"v4-question-{lang}.png"), full_page=True)
                    button.click()
                    expect(page.locator("#result-stage")).to_contain_text(
                        "UNVERIFIED", timeout=10000
                    )
                    assert Fixture.execute_calls - before[0] == 1
                    assert Fixture.poll_calls - before[1] == 2
                    assert Fixture.answer_calls - before[2] == 1
                    cases.append(
                        {
                            "lang": lang,
                            "case": "standalone_synthetic_question_answer",
                            "execute_calls": 1,
                            "job_polls": 2,
                            "answer_calls": 1,
                        }
                    )
                    Fixture.controlled, Fixture.phase = True, "brainstorm"
                    page.goto(base + "/v4")
                    expect(page.locator("#ready-chip")).to_contain_text(
                        "blocked" if lang == "en" else "gesperrt"
                    )
                    expect(page.locator("#execute")).to_be_disabled()
                    expect(page.locator("#send")).to_be_disabled()
                    expect(page.locator('.agent-pill[data-agent="brainstorm"] small')).to_have_text(
                        "blocked" if lang == "en" else "blockiert"
                    )
                    page.set_viewport_size({"width": 1024, "height": 700})
                    page.evaluate("document.body.style.zoom='125%'")
                    page.screenshot(
                        path=str(OUT / f"v4-controlled-blocked-{lang}.png"), full_page=True
                    )
                    page.set_viewport_size({"width": 1440, "height": 900})
                    page.goto(base + "/")
                    expect(page.locator("#llm-badge")).to_contain_text(
                        "blocked" if lang == "en" else "gesperrt", timeout=10000
                    )
                    expect(
                        page.locator('.agent-card[data-agent-id="brainstorm"] .card-status')
                    ).to_have_text("blocked" if lang == "en" else "blockiert")
                    expect(page.locator(".agent-card.is-active")).to_have_count(0)
                    page.locator("#btn-system").click()
                    expect(page.locator("#system-setup")).to_contain_text(
                        "Controlled execution blocked"
                        if lang == "en"
                        else "Kontrollierte Ausführung gesperrt",
                        timeout=10000,
                    )
                    page.screenshot(
                        path=str(OUT / f"legacy-controlled-blocked-{lang}.png"), full_page=True
                    )
                    cases.append(
                        {
                            "lang": lang,
                            "case": "controlled_default_deny_visible_both_surfaces",
                            "send_disabled_v4": True,
                            "execute_disabled_v4": True,
                        }
                    )
                assert not errors, errors
                assert not Fixture.unexpected_posts, Fixture.unexpected_posts
                report = {
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "source_base": "8b8fb43",
                    "source_sha256": {
                        name: hashlib.sha256((STATIC / name).read_bytes()).hexdigest()
                        for name in (
                            "v4.html",
                            "v4.js",
                            "v4.css",
                            "index.html",
                            "app.js",
                            "app.css",
                        )
                    },
                    "kind": "headed_real_chrome_actual_source_isolated_loopback_api_fixture",
                    "production_execution": False,
                    "model_calls": 0,
                    "user_runtime_touched": False,
                    "cases": cases,
                    "page_errors": errors,
                    "unexpected_posts": Fixture.unexpected_posts,
                    "limits": [
                        "synthetic API/job data; no real Gnom execution",
                        "partial DE/EN states only; navigation still contains German",
                        "controlled source remains denied; no issuer/provider/OS acceptance",
                    ],
                }
                (OUT / "browser-proof.json").write_text(json.dumps(report, indent=2) + "\n")
                print(
                    "PASS: headed V4 clarification/answer + controlled denial and legacy System DE/EN; no models"
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
