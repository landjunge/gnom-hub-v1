"""Automated DoD gate checks."""

from __future__ import annotations

from gnom_hub.pipeline.dod_gate import (
    check_worker_draft,
    definition_of_done,
    format_retry_hint,
    html_complete,
    should_retry,
    validate_worker_draft,
)
from gnom_hub.pipeline.dod_lint import lint_dod_prompt, lint_issue_codes


def test_definition_of_done_lint_clean():
    dod = definition_of_done("landing page", ["complete HTML", "User: always dark theme"])
    must = [i for i in lint_dod_prompt(dod) if i.severity == "must"]
    assert must == []
    assert "[!]" in dod


def test_html_complete_parity():
    assert html_complete("<!DOCTYPE html><html><body>x</body></html>")
    assert not html_complete("<html><body>open")


def test_gate_incomplete_html_retryable():
    r = check_worker_draft(
        "<html>partial",
        user_text="landing html page",
        task="build page",
    )
    assert r.ok is False
    assert "incomplete_html" in r.issues
    assert r.retryable is True
    need, why = should_retry(r, user_text="landing html page", task="page")
    assert need and why == "incomplete_html"
    hint = format_retry_hint(r, attempt=1)
    assert "DoD Gate" in hint
    assert not lint_issue_codes(r.issues)


def test_gate_worker_error_no_retry():
    body = "FEHLER: missing API key\nDeliverable: none"
    r = validate_worker_draft(body, user_text="landing html", task="page")
    assert r["ok"] is False
    assert "worker_error" in r["issues"]
    need, _ = should_retry(r, user_text="landing html", task="page")
    assert need is False


def test_gate_wish_missing():
    good_html = (
        "<!DOCTYPE html><html><body>"
        "<button onclick='x()'>Go</button>" + (" content" * 20) + "</body></html>"
    )
    r = check_worker_draft(
        good_html,
        user_text="landing html interactive",
        task="page with click demo",
        requirements=["User: always dark theme with navy blues"],
    )
    # light page without dark → wish_missing
    assert "wish_missing" in r.issues
    assert r.ok is False


def test_gate_wish_dark_reflected():
    body = (
        "<!DOCTYPE html><html><body style='background:#0f172a;color:#e2e8f0'>"
        "<button onclick='go()'>Go</button>" + (" dark theme navy " * 10) + "</body></html>"
    )
    r = check_worker_draft(
        body,
        user_text="landing html interactive demo",
        task="click demo nav",
        requirements=["User: always dark theme"],
    )
    assert "wish_missing" not in r.issues
    assert r.ok is True


def test_gate_prefetch_palette():
    body = (
        "<!DOCTYPE html><html><body>"
        "<button onclick='a()'>A</button>" + (" x" * 40) + "</body></html>"
    )
    tools = [
        {
            "name": "color_palette",
            "ok": True,
            "result": {"primary": "#5b8def", "surface": "#0f172a", "text": "#e6edf3"},
        }
    ]
    r = check_worker_draft(
        body,
        user_text="html landing",
        task="page",
        tool_calls=tools,
    )
    assert "prefetch_palette_unused" in r.issues
    # soft — ok still true if html complete + interaction
    assert r.ok is True
    need, why = should_retry(r, user_text="html landing", task="page")
    assert need and why == "prefetch_palette"

    body2 = body.replace("<body>", "<body style='color:#5b8def'>")
    r2 = check_worker_draft(body2, user_text="html landing", task="page", tool_calls=tools)
    assert "prefetch_palette_unused" not in r2.issues


def test_orchestrator_wrappers():
    from gnom_hub.pipeline.orchestrator import (
        _definition_of_done,
        _html_complete,
        _validate_worker_draft,
    )

    assert "DEFINITION OF DONE" in _definition_of_done("x", ["a"])
    assert _html_complete("<!DOCTYPE html><html><body>z</body></html>")
    bad = _validate_worker_draft("<html>x", user_text="html landing", task="t")
    assert bad["ok"] is False
    assert "score" in bad and "retryable" in bad
