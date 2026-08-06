#!/usr/bin/env python3
"""
Lightweight mutation check for pure Flex/clarify helpers.

Scopes mutations to critical functions only (asserted by this script).
Full-tree mutmut remains optional: ./scripts/run_mutmut.sh

Exit 0 if all in-scope mutants killed; 1 if any survive or baseline fails.
"""

from __future__ import annotations

import ast
import importlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

TARGET_FUNCS = frozenset(
    {
        "_is_flex_meta_requirement",
        "_is_clear_build",
        "_needs_clarify",
        "_has_hedge",
        "_has_tradeoff",
        "_has_decision_seeking",
        "_strip_brainstorm_cta",
    }
)


def _baseline_import() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from gnom_hub.agents.roles_helpers import (
        _is_clear_build,
        _is_flex_meta_requirement,
        _needs_clarify,
    )

    assert _is_flex_meta_requirement("Flex/personal: x") is True
    assert _is_flex_meta_requirement("Flex-wish: User: dark") is False
    assert _is_clear_build("Build a landing page HTML") is True
    assert _needs_clarify("maybe dark mode?") is True
    assert _needs_clarify("Baue eine Todo-App?") is False


def _kill_checks(mod) -> None:
    assert mod._is_flex_meta_requirement("Flex/personal: x") is True
    assert mod._is_flex_meta_requirement("Flex/security: y") is True
    assert mod._is_flex_meta_requirement("Flex-wish: User: dark") is False
    assert mod._is_flex_meta_requirement("User: always TTS") is False
    assert mod._is_clear_build("Build a landing page HTML") is True
    assert mod._is_clear_build("Baue mir eine Todo-App") is True
    assert mod._is_clear_build("hello there") is False
    assert mod._needs_clarify("maybe dark mode") is True
    assert mod._needs_clarify("vielleicht ein Dashboard") is True
    assert mod._needs_clarify("Dark mode?") is True
    assert mod._needs_clarify("Was ist besser?") is True
    assert mod._needs_clarify("Baue eine Todo-App?") is False
    assert mod._needs_clarify("Build a landing page with hero?") is False
    assert mod._needs_clarify("Build a todo app full HTML") is False
    assert mod._needs_clarify("React oder Vue wählen") is True
    assert mod._needs_clarify("Sollen wir Dark Mode nehmen") is True
    # brainstorm decision-seeking only (no hedge/tradeoff words)
    assert (
        mod._needs_clarify(
            "eine einfache App",
            "Sollen wir den Ansatz A nehmen? What do you think about layout?",
        )
        is True
    )
    assert (
        mod._needs_clarify(
            "Checklist app",
            "Variante A oder B. Offene Frage: MVP?",
        )
        is True
    )
    assert (
        mod._needs_clarify(
            "eine App bauen irgendwie",
            "Vielleicht offline-first. Noch unklar ob PWA.",
        )
        is True
    )
    cta = "Ideen\n→ Soll ich das jetzt umsetzen / den Plan erstellen?"
    assert mod._needs_clarify("Build landing HTML", cta) is False
    assert mod._has_hedge("maybe later") is True
    assert mod._has_hedge("eventuell später") is True
    assert mod._has_hedge("solid plan") is False
    assert mod._has_tradeoff("react oder vue") is True
    assert mod._has_tradeoff("mvp oder gründlich") is True
    assert mod._has_tradeoff("mehr oder weniger fertig") is False
    assert mod._has_tradeoff("plain text without choice") is False
    assert mod._has_decision_seeking("sollen wir dark mode") is True
    assert mod._has_decision_seeking("just build it") is False
    stripped = mod._strip_brainstorm_cta(cta + "\nReact oder Vue?")
    assert "umsetzen" not in stripped.lower()
    assert "react" in stripped.lower()


class _ScopedMutate(ast.NodeTransformer):
    def __init__(self, kind: str, index: int) -> None:
        self.kind = kind
        self.index = index
        self.seen = 0
        self.applied = False
        self._func_stack: list[str] = []

    def _in_target(self) -> bool:
        return bool(self._func_stack) and self._func_stack[-1] in TARGET_FUNCS

    def _hit(self) -> bool:
        if not self._in_target():
            return False
        if self.seen == self.index:
            self.applied = True
            self.seen += 1
            return True
        self.seen += 1
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if self.kind == "compare_swap" and len(node.ops) == 1 and self._hit():
            op = node.ops[0]
            swap = {
                ast.Eq: ast.NotEq,
                ast.NotEq: ast.Eq,
                ast.Is: ast.IsNot,
                ast.IsNot: ast.Is,
                ast.In: ast.NotIn,
                ast.NotIn: ast.In,
                ast.Lt: ast.GtE,
                ast.LtE: ast.Gt,
                ast.Gt: ast.LtE,
                ast.GtE: ast.Lt,
            }
            if type(op) in swap:
                node.ops = [swap[type(op)]()]
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if self.kind == "not_drop" and isinstance(node.op, ast.Not) and self._hit():
            return node.operand
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self.kind == "bool_flip" and isinstance(node.value, bool) and self._hit():
            return ast.copy_location(ast.Constant(value=not node.value), node)
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        if not self._in_target():
            return node
        if self.kind == "return_invert" and self._hit():
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                return ast.copy_location(
                    ast.Return(value=ast.Constant(value=not node.value.value)),
                    node,
                )
            if node.value is not None:
                return ast.copy_location(
                    ast.Return(value=ast.UnaryOp(op=ast.Not(), operand=node.value)),
                    node,
                )
        return node


def _count(kind: str, tree: ast.AST) -> int:
    m = _ScopedMutate(kind, 10_000)
    m.visit(tree)
    return m.seen


def _purge_gnom() -> None:
    for key in list(sys.modules):
        if key == "gnom_hub" or key.startswith("gnom_hub."):
            del sys.modules[key]


def _load_mutated(source: str):
    td = Path(tempfile.mkdtemp(prefix="mut_"))
    pkg = td / "gnom_hub" / "agents"
    pkg.mkdir(parents=True)
    (td / "gnom_hub" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "roles_helpers.py").write_text(source, encoding="utf-8")
    while str(SRC) in sys.path:
        sys.path.remove(str(SRC))
    sys.path.insert(0, str(td))
    _purge_gnom()
    mod = importlib.import_module("gnom_hub.agents.roles_helpers")
    return mod, td


def run() -> int:
    print("mutation_check: baseline…")
    _baseline_import()
    print("mutation_check: baseline OK")

    original = (ROOT / "src/gnom_hub/agents/roles_helpers.py").read_text(encoding="utf-8")
    kinds = ("compare_swap", "not_drop", "bool_flip", "return_invert")
    killed = 0
    survived: list[str] = []
    total = 0
    temps: list[Path] = []

    for kind in kinds:
        n = _count(kind, ast.parse(original))
        for i in range(n):
            total += 1
            mut = _ScopedMutate(kind, i)
            tree = mut.visit(ast.parse(original))
            if not mut.applied:
                continue
            ast.fix_missing_locations(tree)
            try:
                source = ast.unparse(tree)
            except Exception:
                killed += 1
                continue
            try:
                mod, td = _load_mutated(source)
                temps.append(td)
            except Exception as exc:
                killed += 1
                print(f"  killed {kind}#{i} (import {type(exc).__name__})")
                continue
            try:
                _kill_checks(mod)
            except AssertionError:
                killed += 1
                print(f"  killed {kind}#{i}")
                continue
            except Exception as exc:
                killed += 1
                print(f"  killed {kind}#{i} ({type(exc).__name__})")
                continue
            survived.append(f"{kind}#{i}")
            print(f"  SURVIVED {kind}#{i}")

    for td in temps:
        shutil.rmtree(td, ignore_errors=True)

    _purge_gnom()
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    print()
    print(f"in-scope mutants={total} killed={killed} survived={len(survived)}")
    if survived:
        print("SURVIVORS:")
        for s in survived:
            print(" ", s)
        rate = killed / total if total else 1.0
        print(f"kill_rate={rate:.1%}")
        return 1
    print("All in-scope mutants killed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
