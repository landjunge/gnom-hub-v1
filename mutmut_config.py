"""
In-process mutmut hooks (optional).

mutmut imports this module from the project root if present:
  pre_mutation(context=...)  — set context.skip = True to exclude a mutant

Shell hooks: scripts/mutmut_hooks.py (pycache / backups).
"""

from __future__ import annotations


def pre_mutation(context) -> None:
    """
    Skip mutants that the focused suite cannot sensibly kill.

    Markers in source:  # mutmut skip   or   # pragma: no mutmut
    """
    line = (getattr(context, "current_source_line", None) or "").strip()
    if not line:
        context.skip = True
        return
    low = line.lower()
    if "mutmut skip" in low or "pragma: no mutmut" in low:
        context.skip = True
        return
    if line.startswith("#"):
        context.skip = True
        return
    # single-line docstring
    if len(line) >= 6 and (
        (line.startswith('"""') and line.endswith('"""'))
        or (line.startswith("'''") and line.endswith("'''"))
    ):
        context.skip = True
        return
    if line.startswith("print(") and "debug" in low:
        context.skip = True
