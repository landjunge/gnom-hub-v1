"""DoD lint rules — stable codes + structure checks for Definition-of-Done.

Two layers:

1. **Rule catalog** (``DOD_LINT_RULES``) — machine-stable issue codes the gate emits.
2. **Structure lint** (``lint_dod_structure``) — validates DoD *spec/prompt shape*
   so prompt inject and gate stay aligned.

See docs/DOD_LINT.md and docs/DOD_GATE_PLAN.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal

Severity = Literal["must", "should", "info"]
Category = Literal["honesty", "html", "wish", "prefetch", "req", "structure", "meta"]

# Stable id pattern for checklist / issue codes
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
_WISH_CODE_RE = re.compile(r"^wish_[a-z0-9_]{2,40}$")
_REQ_CODE_RE = re.compile(r"^req_\d{1,3}$")

# DoD prompt markers (must stay in sync with render_dod_prompt / _definition_of_done)
DOD_MARK_START = "=== DEFINITION OF DONE (mandatory) ==="
DOD_MARK_END = "=== END DoD ==="
DOD_CHECK_MUST = re.compile(r"^\s*\[\s*\]\s+\S", re.MULTILINE)
DOD_CHECK_ABS = re.compile(r"^\s*\[!\]\s+\S", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class DodLintRule:
    """One lint rule the DoD gate may emit."""

    code: str
    severity: Severity
    category: Category
    applies_when: str  # always | html | has_wishes | has_palette | has_reqs
    message: str
    hint: str
    retryable: bool
    weight: int = 10  # for scoring; higher = more important

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Catalog (codes are API contract — do not rename lightly) ──────────

DOD_LINT_RULES: tuple[DodLintRule, ...] = (
    # honesty
    DodLintRule(
        code="worker_error",
        severity="must",
        category="honesty",
        applies_when="always",
        message="Worker returned FEHLER / no deliverable (auth or provider).",
        hint="Set a real DEEPSEEK_API_KEY; re-run Execute. Do not invent stubs.",
        retryable=False,
        weight=100,
    ),
    DodLintRule(
        code="stub",
        severity="must",
        category="honesty",
        applies_when="always",
        message="Stub output is not a deliverable.",
        hint="Produce a real result for the user task.",
        retryable=False,
        weight=90,
    ),
    DodLintRule(
        code="too_short",
        severity="must",
        category="honesty",
        applies_when="always",
        message="Output too short to count as done.",
        hint="Expand to a complete deliverable (structure + core behavior).",
        retryable=True,
        weight=40,
    ),
    DodLintRule(
        code="truncated_ellipsis",
        severity="must",
        category="honesty",
        applies_when="always",
        message="Output ends with ellipsis / looks truncated.",
        hint="Finish the document; never end mid-tag or with '...'.",
        retryable=True,
        weight=50,
    ),
    # html
    DodLintRule(
        code="incomplete_html",
        severity="must",
        category="html",
        applies_when="html",
        message="HTML document incomplete (missing doctype/html or bad close).",
        hint="ONE complete file: <!DOCTYPE html> … </html>; close style/script.",
        retryable=True,
        weight=80,
    ),
    DodLintRule(
        code="missing_html_close",
        severity="must",
        category="html",
        applies_when="html",
        message="Missing </html> close tag.",
        hint="End the file with </html>; cut CSS if needed.",
        retryable=True,
        weight=70,
    ),
    DodLintRule(
        code="missing_required_interaction",
        severity="must",
        category="html",
        applies_when="html",
        message="Required interaction missing (task asked for interactive UI).",
        hint="Add at least one onclick= or addEventListener (or form submit handler).",
        retryable=True,
        weight=65,
    ),
    DodLintRule(
        code="no_interaction",
        severity="should",
        category="html",
        applies_when="html",
        message="No interactive handler found.",
        hint="Prefer a small working control over pure static markup.",
        retryable=True,
        weight=25,
    ),
    DodLintRule(
        code="css_before_functions",
        severity="should",
        category="html",
        applies_when="html",
        message="Heavy CSS without meaningful JS/interaction.",
        hint="Drop decoration; implement 1–3 core interactions first.",
        retryable=True,
        weight=20,
    ),
    # wish
    DodLintRule(
        code="wish_missing",
        severity="must",
        category="wish",
        applies_when="has_wishes",
        message="Absolute user wish not reflected in deliverable.",
        hint="Implement standing User:/Wish: lines fully — no optional.",
        retryable=True,
        weight=75,
    ),
    # prefetch
    DodLintRule(
        code="prefetch_palette_unused",
        severity="should",
        category="prefetch",
        applies_when="has_palette",
        message="Design prefetch palette not used in deliverable.",
        hint="Reuse prefetched --color-* vars or primary hex; do not invent a second palette.",
        retryable=True,
        weight=30,
    ),
    DodLintRule(
        code="prefetch_scaffold_ignored",
        severity="info",
        category="prefetch",
        applies_when="has_scaffold",
        message="html_scaffold was prefetched but structure looks unrelated.",
        hint="Keep scaffold landmarks (header/main/footer or layout) when useful.",
        retryable=False,
        weight=10,
    ),
    # requirements
    DodLintRule(
        code="req_unmatched",
        severity="should",
        category="req",
        applies_when="has_reqs",
        message="One or more DoD requirements have weak match in body.",
        hint="Cover MUSS requirements explicitly in the deliverable.",
        retryable=False,
        weight=15,
    ),
    # multi-worker / plan
    DodLintRule(
        code="multi_html_collision",
        severity="should",
        category="meta",
        applies_when="always",
        message="Multiple workers produced full HTML pages.",
        hint="Only one worker should own the HTML page (coordinator plan).",
        retryable=False,
        weight=20,
    ),
)

# Index
_RULES_BY_CODE: dict[str, DodLintRule] = {r.code: r for r in DOD_LINT_RULES}


def rule_by_code(code: str) -> DodLintRule | None:
    return _RULES_BY_CODE.get(str(code or "").strip())


def rules_for(
    *,
    applies_when: str | None = None,
    category: Category | None = None,
    severity: Severity | None = None,
) -> list[DodLintRule]:
    out: list[DodLintRule] = []
    for r in DOD_LINT_RULES:
        if applies_when is not None and r.applies_when != applies_when:
            continue
        if category is not None and r.category != category:
            continue
        if severity is not None and r.severity != severity:
            continue
        out.append(r)
    return out


def catalog() -> list[dict[str, Any]]:
    """JSON-serializable rule list (API / docs / UI)."""
    return [r.as_dict() for r in DOD_LINT_RULES]


def known_codes() -> frozenset[str]:
    return frozenset(_RULES_BY_CODE)


# ── Structure lint: DoD prompt / checklist shape ──────────────────────


@dataclass(slots=True)
class StructureIssue:
    code: str
    severity: Severity
    message: str
    path: str = ""  # e.g. items[2].id

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _valid_item_id(item_id: str) -> bool:
    s = str(item_id or "").strip()
    return bool(_CODE_RE.match(s) or _WISH_CODE_RE.match(s) or _REQ_CODE_RE.match(s))


def lint_dod_spec(spec: Any) -> list[StructureIssue]:
    """
    Lint a DoDSpec-like object or dict for structural integrity.

    Accepts:
      - mapping with keys: items, wants_html, wishes, ...
      - object with attributes
      - list of item dicts (items only)
    """
    issues: list[StructureIssue] = []

    if spec is None:
        return [
            StructureIssue(
                code="spec_missing",
                severity="must",
                message="DoDSpec is None",
                path="$",
            )
        ]

    def g(name: str, default: Any = None) -> Any:
        if isinstance(spec, dict):
            return spec.get(name, default)
        return getattr(spec, name, default)

    items = g("items", None)
    if items is None and isinstance(spec, list):
        items = spec
    if not isinstance(items, (list, tuple)):
        issues.append(
            StructureIssue(
                code="spec_items_type",
                severity="must",
                message="spec.items must be a list",
                path="items",
            )
        )
        items = []

    if len(items) == 0:
        issues.append(
            StructureIssue(
                code="spec_items_empty",
                severity="must",
                message="DoDSpec.items is empty — gate has nothing to check",
                path="items",
            )
        )

    seen_ids: set[str] = set()
    must_n = 0
    for i, raw in enumerate(items):
        path = f"items[{i}]"
        if isinstance(raw, dict):
            iid = str(raw.get("id") or "")
            sev = str(raw.get("severity") or "must")
            label = str(raw.get("label") or "")
            kind = str(raw.get("kind") or raw.get("category") or "")
        else:
            iid = str(getattr(raw, "id", "") or "")
            sev = str(getattr(raw, "severity", "must") or "must")
            label = str(getattr(raw, "label", "") or "")
            kind = str(getattr(raw, "kind", "") or getattr(raw, "category", "") or "")

        if not iid:
            issues.append(
                StructureIssue(
                    code="item_id_missing",
                    severity="must",
                    message="item.id is required",
                    path=f"{path}.id",
                )
            )
        elif not _valid_item_id(iid):
            issues.append(
                StructureIssue(
                    code="item_id_invalid",
                    severity="must",
                    message=f"item.id {iid!r} must match [a-z][a-z0-9_]{{1,47}} "
                    f"or wish_* / req_N",
                    path=f"{path}.id",
                )
            )
        elif iid in seen_ids:
            issues.append(
                StructureIssue(
                    code="item_id_duplicate",
                    severity="must",
                    message=f"duplicate item.id {iid!r}",
                    path=f"{path}.id",
                )
            )
        else:
            seen_ids.add(iid)

        if sev not in ("must", "should", "info"):
            issues.append(
                StructureIssue(
                    code="item_severity_invalid",
                    severity="must",
                    message=f"severity must be must|should|info, got {sev!r}",
                    path=f"{path}.severity",
                )
            )
        if sev == "must":
            must_n += 1

        if not label or len(label.strip()) < 3:
            issues.append(
                StructureIssue(
                    code="item_label_short",
                    severity="should",
                    message="item.label should be a short human phrase (≥3 chars)",
                    path=f"{path}.label",
                )
            )

        if kind and kind not in (
            "honesty",
            "html",
            "wish",
            "prefetch",
            "req",
            "structure",
            "meta",
        ):
            issues.append(
                StructureIssue(
                    code="item_kind_unknown",
                    severity="info",
                    message=f"unknown kind {kind!r}",
                    path=f"{path}.kind",
                )
            )

    if items and must_n == 0:
        issues.append(
            StructureIssue(
                code="spec_no_must",
                severity="should",
                message="No severity=must items — gate cannot hard-fail",
                path="items",
            )
        )

    wants_html = bool(g("wants_html", False))
    if wants_html:
        html_ids = {i for i in seen_ids if i.startswith("html") or i in (
            "incomplete_html",
            "missing_html_close",
            "missing_required_interaction",
            "html_complete",
            "html_interaction",
        )}
        # accept either catalog codes or html_* checklist ids
        if not html_ids and "incomplete_html" not in seen_ids and "html_complete" not in seen_ids:
            issues.append(
                StructureIssue(
                    code="spec_html_without_items",
                    severity="must",
                    message="wants_html=True but no HTML checklist items",
                    path="wants_html",
                )
            )

    wishes = g("wishes", None) or []
    if wishes and not any(i.startswith("wish") for i in seen_ids):
        issues.append(
            StructureIssue(
                code="spec_wishes_without_items",
                severity="should",
                message="spec.wishes set but no wish_* checklist items",
                path="wishes",
            )
        )

    return issues


def lint_dod_prompt(text: str) -> list[StructureIssue]:
    """Lint the human DoD prompt block workers receive."""
    issues: list[StructureIssue] = []
    s = text or ""
    if DOD_MARK_START not in s:
        issues.append(
            StructureIssue(
                code="prompt_missing_start",
                severity="must",
                message=f"DoD prompt missing start marker: {DOD_MARK_START}",
                path="prompt",
            )
        )
    if DOD_MARK_END not in s:
        issues.append(
            StructureIssue(
                code="prompt_missing_end",
                severity="must",
                message=f"DoD prompt missing end marker: {DOD_MARK_END}",
                path="prompt",
            )
        )
    if (
        DOD_MARK_START in s
        and DOD_MARK_END in s
        and s.find(DOD_MARK_START) > s.find(DOD_MARK_END)
    ):
        issues.append(
            StructureIssue(
                code="prompt_marker_order",
                severity="must",
                message="END marker appears before START marker",
                path="prompt",
            )
        )
    must_checks = DOD_CHECK_MUST.findall(s)
    if len(must_checks) < 1:
        issues.append(
            StructureIssue(
                code="prompt_no_checkboxes",
                severity="should",
                message="DoD prompt has no '[ ] …' checklist lines",
                path="prompt",
            )
        )
    # Absolute wishes should use [!]
    if re.search(r"(?i)standing wish|absolute|flex-wish:|user:", s) and not DOD_CHECK_ABS.search(
        s
    ):
        issues.append(
            StructureIssue(
                code="prompt_wishes_not_absolute_marked",
                severity="should",
                message="Wish language present but no '[!] …' absolute lines",
                path="prompt",
            )
        )
    if len(s) > 6000:
        issues.append(
            StructureIssue(
                code="prompt_too_long",
                severity="info",
                message=f"DoD prompt is large ({len(s)} chars) — may crowd worker context",
                path="prompt",
            )
        )
    return issues


def lint_issue_codes(codes: Iterable[str]) -> list[StructureIssue]:
    """Ensure emitted issue codes are in the catalog (or wish_/req_ dynamic)."""
    issues: list[StructureIssue] = []
    known = known_codes()
    for raw in codes or []:
        c = str(raw or "").strip()
        if not c:
            issues.append(
                StructureIssue(
                    code="issue_code_empty",
                    severity="must",
                    message="empty issue code",
                    path="issues",
                )
            )
            continue
        if c in known:
            continue
        if _WISH_CODE_RE.match(c) or _REQ_CODE_RE.match(c):
            continue
        # allow dynamic wish_missing with suffix? keep strict: wish_missing is catalog
        issues.append(
            StructureIssue(
                code="issue_code_unknown",
                severity="must",
                message=f"unknown DoD issue code {c!r} — not in DOD_LINT_RULES",
                path=f"issues.{c}",
            )
        )
    return issues


def assert_catalog_integrity() -> None:
    """Raise AssertionError if the rule catalog is inconsistent (tests / startup)."""
    if len(DOD_LINT_RULES) != len(_RULES_BY_CODE):
        raise AssertionError("duplicate codes in DOD_LINT_RULES")
    for r in DOD_LINT_RULES:
        if not _CODE_RE.match(r.code):
            raise AssertionError(f"invalid rule code: {r.code}")
        if r.severity not in ("must", "should", "info"):
            raise AssertionError(f"bad severity on {r.code}")
        if r.weight < 0:
            raise AssertionError(f"negative weight on {r.code}")
        if not r.message or not r.hint:
            raise AssertionError(f"message/hint required on {r.code}")


def score_from_issues(codes: Iterable[str], *, base: int = 100) -> int:
    """Simple 0–100 score: subtract rule weights for failed codes."""
    score = base
    for c in codes or []:
        rule = rule_by_code(str(c))
        if rule:
            score -= rule.weight
        else:
            score -= 5
    return max(0, min(100, score))


def retryable_from_issues(codes: Iterable[str]) -> bool:
    """True if any failed code is retryable (unknown codes → True)."""
    for c in codes or []:
        rule = rule_by_code(str(c))
        if rule is None:
            return True
        if rule.retryable:
            return True
    return False


def hints_for_issues(codes: Iterable[str], *, limit: int = 6) -> list[str]:
    out: list[str] = []
    for c in codes or []:
        rule = rule_by_code(str(c))
        if rule and rule.hint:
            out.append(f"{rule.code}: {rule.hint}")
        elif c:
            out.append(f"{c}: fix this DoD item")
        if len(out) >= limit:
            break
    return out


# Run integrity at import for fail-fast in tests (cheap)
assert_catalog_integrity()
