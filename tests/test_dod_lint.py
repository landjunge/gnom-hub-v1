"""DoD lint rule catalog + structure checks."""

from __future__ import annotations

from gnom_hub.pipeline.dod_lint import (
    DOD_LINT_RULES,
    DOD_MARK_END,
    DOD_MARK_START,
    assert_catalog_integrity,
    catalog,
    hints_for_issues,
    known_codes,
    lint_dod_prompt,
    lint_dod_spec,
    lint_issue_codes,
    retryable_from_issues,
    rule_by_code,
    rules_for,
    score_from_issues,
)


def test_catalog_integrity():
    assert_catalog_integrity()
    assert len(DOD_LINT_RULES) >= 10
    assert "worker_error" in known_codes()
    assert "incomplete_html" in known_codes()
    assert rule_by_code("worker_error").retryable is False
    assert rule_by_code("incomplete_html").retryable is True


def test_catalog_jsonable():
    cat = catalog()
    assert isinstance(cat, list)
    assert all("code" in r and "severity" in r for r in cat)


def test_rules_for_filters():
    html = rules_for(applies_when="html")
    assert any(r.code == "incomplete_html" for r in html)
    musts = rules_for(severity="must")
    assert all(r.severity == "must" for r in musts)


def test_lint_dod_spec_happy():
    spec = {
        "wants_html": True,
        "wishes": ["User: always dark theme"],
        "items": [
            {"id": "html_complete", "severity": "must", "label": "Complete HTML", "kind": "html"},
            {
                "id": "wish_dark_theme",
                "severity": "must",
                "label": "Dark theme",
                "kind": "wish",
            },
            {"id": "too_short", "severity": "must", "label": "Enough content", "kind": "honesty"},
        ],
    }
    issues = lint_dod_spec(spec)
    musts = [i for i in issues if i.severity == "must"]
    assert musts == [], musts


def test_lint_dod_spec_rejects_bad_ids_and_empty():
    issues = lint_dod_spec({"items": []})
    codes = {i.code for i in issues}
    assert "spec_items_empty" in codes

    issues2 = lint_dod_spec(
        {
            "wants_html": True,
            "items": [
                {"id": "Bad-Id!", "severity": "must", "label": "x"},
                {"id": "ok_id", "severity": "maybe", "label": "ok label"},
            ],
        }
    )
    codes2 = {i.code for i in issues2}
    assert "item_id_invalid" in codes2
    assert "item_severity_invalid" in codes2
    assert "spec_html_without_items" in codes2


def test_lint_dod_spec_duplicate_ids():
    issues = lint_dod_spec(
        {
            "items": [
                {"id": "html_complete", "severity": "must", "label": "A"},
                {"id": "html_complete", "severity": "must", "label": "B"},
            ]
        }
    )
    assert any(i.code == "item_id_duplicate" for i in issues)


def test_lint_dod_prompt_markers():
    good = f"{DOD_MARK_START}\n  [ ] Complete HTML\n  [!] User: dark\n{DOD_MARK_END}"
    assert lint_dod_prompt(good) == []

    bad = "just some text without markers\n  [ ] item"
    codes = {i.code for i in lint_dod_prompt(bad)}
    assert "prompt_missing_start" in codes
    assert "prompt_missing_end" in codes


def test_lint_issue_codes_unknown():
    issues = lint_issue_codes(["incomplete_html", "not_a_real_code", "wish_abc", "req_1"])
    codes = {i.code for i in issues}
    assert "issue_code_unknown" in codes
    # only not_a_real_code should fail
    assert len([i for i in issues if i.code == "issue_code_unknown"]) == 1


def test_score_and_retryable_hints():
    codes = ["incomplete_html", "no_interaction"]
    assert score_from_issues(codes) < 100
    assert retryable_from_issues(codes) is True
    assert retryable_from_issues(["worker_error"]) is False
    hints = hints_for_issues(codes)
    assert any("incomplete_html" in h for h in hints)


def test_existing_definition_of_done_passes_prompt_lint():
    from gnom_hub.pipeline.orchestrator import _definition_of_done

    dod = _definition_of_done(
        "Build landing page",
        ["complete HTML", "User: always dark theme", "Flex meta skip this"],
    )
    issues = lint_dod_prompt(dod)
    # should have markers + checkboxes; wishes use [!] when wish lines present
    musts = [i for i in issues if i.severity == "must"]
    assert musts == [], musts
