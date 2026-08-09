#!/usr/bin/env python3
"""Validate Mermaid blocks in Gnom-Hub markdown (static, no Node required).

Usage:
  python scripts/mermaid_check.py              # check all default roots
  python scripts/mermaid_check.py --list       # inventory
  python scripts/mermaid_check.py --json       # machine report
  python scripts/mermaid_check.py path.md ...  # explicit files
  python scripts/mermaid_check.py --write-inventory docs/generated/mermaid_inventory.md

Exit 0 = ok, 1 = errors, 2 = usage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GLOBS = (
    "README.md",
    "README_DE.md",
    "docs/**/*.md",
)

ALLOWED_DIAGRAMS = (
    "flowchart",
    "graph",  # legacy alias — warn only
    "stateDiagram-v2",
    "stateDiagram",
    "sequenceDiagram",
)

BANNED_PATTERNS = (
    (re.compile(r"\bclick\s+\w+", re.IGNORECASE), "click handlers not supported on GitHub"),
    (re.compile(r"\bgitGraph\b"), "gitGraph not used in this repo"),
    (re.compile(r"\bgantt\b", re.IGNORECASE), "gantt not used in this repo"),
    (re.compile(r"\bpien\b"), "pie charts not used"),  # avoid matching 'piece'
    (re.compile(r"^\s*pie\b", re.MULTILINE), "pie charts not used"),
    (re.compile(r"\bjourney\b", re.IGNORECASE), "journey not used"),
    (re.compile(r"\bmindmap\b", re.IGNORECASE), "mindmap not used"),
    (re.compile(r"\bC4Context\b"), "C4 diagrams not used"),
)

# Shared palette — must match docs/MERMAID.md §5
ALLOWED_CLASSES = frozenset(
    {
        "ui",
        "core",
        "locked",
        "work",
        "hot",
        "warm",
        "cold",
        "store",
        "plugin",
        "danger",
        "gate",
        "terminal",
    }
)

# Legacy aliases we reject so docs stay consistent
BANNED_CLASSES = frozenset({"edge", "reg", "default"})

FENCE_RE = re.compile(
    r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
CLASSDEF_RE = re.compile(r"classDef\s+(\w+)\b")
CLASS_APPLY_RE = re.compile(r"(?:^|\s)class\s+([\w,\s]+?)\s+(\w+)\s*$", re.MULTILINE)
SHORTHAND_RE = re.compile(r":::\s*(\w+)")
BACKSLASH_N_RE = re.compile(r'"[^"]*\\n[^"]*"')
ACTIVATE_RE = re.compile(r"^\s*activate\s+\w+", re.MULTILINE)
DEACTIVATE_RE = re.compile(r"^\s*deactivate\s+\w+", re.MULTILINE)


@dataclass
class Issue:
    level: str  # error | warning
    code: str
    message: str
    line: int | None = None


@dataclass
class Block:
    path: str
    index: int
    start_line: int
    body: str
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]


def _line_of(body: str, offset: int, base_line: int) -> int:
    return base_line + body.count("\n", 0, offset)


def discover_files(root: Path, explicit: list[str]) -> list[Path]:
    if explicit:
        out = []
        for e in explicit:
            p = Path(e)
            if not p.is_absolute():
                p = (root / p).resolve()
            if p.is_file():
                out.append(p)
        return sorted(set(out))
    found: set[Path] = set()
    for pattern in DEFAULT_GLOBS:
        if "**" in pattern:
            found.update(root.glob(pattern))
        else:
            p = root / pattern
            if p.is_file():
                found.add(p)
    # skip generated inventory itself for class rules? still check mermaid if any
    return sorted(p for p in found if p.is_file() and p.suffix.lower() == ".md")


def extract_blocks(path: Path, root: Path) -> list[Block]:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    blocks: list[Block] = []
    for i, m in enumerate(FENCE_RE.finditer(text), start=1):
        start_line = text.count("\n", 0, m.start()) + 1
        body = m.group(1).strip("\n")
        blocks.append(Block(path=rel, index=i, start_line=start_line, body=body))
    return blocks


def _strip_frontmatter(body: str) -> tuple[str, int]:
    """Return body without --- frontmatter and lines consumed."""
    if not body.startswith("---"):
        return body, 0
    lines = body.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return body, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            rest = "\n".join(lines[i + 1 :])
            return rest.lstrip("\n"), i + 1
    return body, 0


def validate_block(block: Block) -> None:
    body = block.body
    if not body.strip():
        block.issues.append(Issue("error", "empty", "empty mermaid block"))
        return

    stripped, fm_lines = _strip_frontmatter(body)
    work = stripped.strip()
    if not work:
        block.issues.append(Issue("error", "empty_after_fm", "only frontmatter, no diagram"))
        return

    first = work.lstrip().splitlines()[0].strip()
    # drop comments
    while first.startswith("%%"):
        rest_lines = work.lstrip().splitlines()[1:]
        work = "\n".join(rest_lines)
        if not work.strip():
            block.issues.append(Issue("error", "empty", "only comments"))
            return
        first = work.lstrip().splitlines()[0].strip()

    kind = first.split()[0] if first.split() else ""
    # flowchart TB → kind flowchart
    if kind not in ALLOWED_DIAGRAMS and not any(first.startswith(k) for k in ALLOWED_DIAGRAMS):
        block.issues.append(
            Issue(
                "error",
                "unknown_diagram",
                f"first diagram keyword {kind!r} not in {ALLOWED_DIAGRAMS}",
                line=block.start_line + fm_lines + 1,
            )
        )
    if kind == "graph" or first.startswith("graph "):
        block.issues.append(
            Issue(
                "warning",
                "legacy_graph",
                "prefer flowchart over legacy graph",
                line=block.start_line + fm_lines + 1,
            )
        )

    for rx, msg in BANNED_PATTERNS:
        if rx.search(body):
            block.issues.append(Issue("error", "banned", msg))

    if BACKSLASH_N_RE.search(body):
        block.issues.append(
            Issue(
                "error",
                "backslash_n",
                r"quoted label contains \n — use <br/> instead",
            )
        )

    # classDef names
    for m in CLASSDEF_RE.finditer(body):
        name = m.group(1)
        if name in BANNED_CLASSES:
            block.issues.append(
                Issue(
                    "error",
                    "banned_class",
                    f"classDef {name!r} is banned — use shared palette",
                    line=_line_of(body, m.start(), block.start_line),
                )
            )
        elif name not in ALLOWED_CLASSES:
            block.issues.append(
                Issue(
                    "error",
                    "unknown_class",
                    f"classDef {name!r} not in Gnom palette {sorted(ALLOWED_CLASSES)}",
                    line=_line_of(body, m.start(), block.start_line),
                )
            )

    for m in SHORTHAND_RE.finditer(body):
        name = m.group(1)
        if name in BANNED_CLASSES or name not in ALLOWED_CLASSES:
            block.issues.append(
                Issue(
                    "error",
                    "unknown_shorthand",
                    f":::{name} not in Gnom palette",
                    line=_line_of(body, m.start(), block.start_line),
                )
            )

    for m in CLASS_APPLY_RE.finditer(body):
        cname = m.group(2)
        if cname not in ALLOWED_CLASSES:
            block.issues.append(
                Issue(
                    "error",
                    "unknown_class_apply",
                    f"class … {cname} not in Gnom palette",
                    line=_line_of(body, m.start(), block.start_line),
                )
            )

    # sequence activate balance
    if "sequenceDiagram" in body:
        act = len(ACTIVATE_RE.findall(body))
        deact = len(DEACTIVATE_RE.findall(body))
        # +/- message form also activates — only warn if explicit activate used
        if (act or deact) and act != deact:
            block.issues.append(
                Issue(
                    "warning",
                    "activate_balance",
                    f"activate={act} deactivate={deact} (should match)",
                )
            )

    # flowchart with classDef should use stroke-width (style depth)
    if CLASSDEF_RE.search(body):
        for m in re.finditer(
            r"classDef\s+\w+\s+([^\n]+)",
            body,
        ):
            props = m.group(1)
            if "stroke-width" not in props:
                block.issues.append(
                    Issue(
                        "warning",
                        "stroke_width",
                        "classDef missing stroke-width (see MERMAID.md palette)",
                        line=_line_of(body, m.start(), block.start_line),
                    )
                )


def write_inventory(blocks: list[Block], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "<!-- Generated by scripts/mermaid_check.py --write-inventory; do not edit -->",
        "# Mermaid inventory",
        "",
        f"Blocks: **{len(blocks)}**",
        "",
        "| File | # | Line | Kind | Errors | Warnings |",
        "|------|---|------|------|--------|----------|",
    ]
    for b in blocks:
        kind = "?"
        stripped, _ = _strip_frontmatter(b.body)
        first = stripped.strip().splitlines()[0] if stripped.strip() else ""
        if first:
            kind = first.split()[0]
        lines.append(
            f"| `{b.path}` | {b.index} | {b.start_line} | `{kind}` | "
            f"{len(b.errors)} | {len(b.warnings)} |"
        )
    lines.append("")
    lines.append("Regenerate: `python scripts/mermaid_check.py --write-inventory`")
    lines.append("")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="Markdown files (default: README + docs/)")
    ap.add_argument("--list", action="store_true", help="Print inventory")
    ap.add_argument("--json", action="store_true", help="JSON report on stdout")
    ap.add_argument(
        "--write-inventory",
        metavar="PATH",
        help="Write markdown inventory (e.g. docs/generated/mermaid_inventory.md)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    ap.add_argument(
        "--root",
        default=str(ROOT),
        help="Repo root (default: auto)",
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    files = discover_files(root, args.paths)
    if not files:
        print("mermaid_check: no markdown files found", file=sys.stderr)
        return 2

    blocks: list[Block] = []
    for f in files:
        blocks.extend(extract_blocks(f, root))

    for b in blocks:
        validate_block(b)

    if args.write_inventory:
        inv = Path(args.write_inventory)
        if not inv.is_absolute():
            inv = root / inv
        write_inventory(blocks, inv)
        try:
            shown = inv.relative_to(root)
        except ValueError:
            shown = inv
        print(f"wrote {shown}")

    err_n = sum(len(b.errors) for b in blocks)
    warn_n = sum(len(b.warnings) for b in blocks)

    if args.json:
        payload = {
            "files": len(files),
            "blocks": len(blocks),
            "errors": err_n,
            "warnings": warn_n,
            "items": [
                {
                    **asdict(b),
                    "issues": [asdict(i) for i in b.issues],
                }
                for b in blocks
            ],
        }
        print(json.dumps(payload, indent=2))
    elif args.list:
        for b in blocks:
            kind = b.body.strip().splitlines()[0][:40] if b.body.strip() else "?"
            flag = "ERR" if b.errors else ("WARN" if b.warnings else "ok")
            print(f"[{flag}] {b.path}:{b.start_line} #{b.index} {kind!r}")
    else:
        print(f"mermaid_check: {len(files)} files · {len(blocks)} blocks")
        for b in blocks:
            for iss in b.issues:
                loc = f"{b.path}:{iss.line or b.start_line}"
                print(f"  {iss.level.upper():7} {loc} [{iss.code}] {iss.message}")
        if err_n == 0 and warn_n == 0:
            print("✅ all mermaid blocks ok")
        else:
            print(f"→ {err_n} error(s), {warn_n} warning(s)")

    if err_n:
        return 1
    if args.strict and warn_n:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
