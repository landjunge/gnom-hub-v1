"""Unit tests for memory/requirement dedupe strategies."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.memory.dedupe import (
    already_covered,
    core_key,
    dedupe_texts,
    exact_key,
    merge_unique,
    prefer_canonical_wish,
    requirement_key,
    strip_fact_prefixes,
)
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory


def test_strip_and_core_keys():
    assert strip_fact_prefixes("Flex-wish: User: dark theme") == "dark theme"
    assert core_key("User: always DE") == core_key("Wish: always DE.")
    assert core_key("Flex-wish: User: ruff before push") == "ruff before push"
    assert exact_key("  Foo  Bar ") == "foo bar"
    assert requirement_key("Flex-wish: User: x") == requirement_key("User: x")


def test_dedupe_texts_strategies():
    items = [
        "User: always enable dark theme",
        "Flex-wish: User: always enable dark theme",
        "User: always enable dark theme.",
        "Ziel: landing page",
        "ziel: landing page",  # exact differs; core collapses
    ]
    exact = dedupe_texts(items, strategy="exact")
    assert len(exact) == 4  # trailing punct differs on third? "theme." vs "theme"
    # third has trailing period → different exact key
    assert exact[0].startswith("User:")

    core = dedupe_texts(items, strategy="core")
    assert len(core) == 2
    assert core[0] == "User: always enable dark theme"
    assert "landing" in core[1].lower()


def test_already_covered_and_merge():
    base = ["Ziel: Bean Shop", "User: prefers German"]
    assert already_covered("Flex-wish: User: prefers German", base)
    assert not already_covered("User: always dark theme", base)
    merged = merge_unique(
        base, ["Flex-wish: User: prefers German", "User: always dark"], strategy="requirement"
    )
    assert merged == ["Ziel: Bean Shop", "User: prefers German", "User: always dark"]


def test_prefer_canonical_wish():
    assert prefer_canonical_wish("Flex-wish: User:  dark  ") == "User: dark"
    assert prefer_canonical_wish("") == ""


def test_warm_flex_core_dedupe(tmp_path: Path):
    warm = WarmMemory(tmp_path, max_facts=50)
    assert warm.add_fact("User: always enable dark theme", source="flex") is True
    # prefix / punct variant must not insert again
    assert warm.add_fact("Flex-wish: User: always enable dark theme.", source="flex") is False
    assert warm.add_fact("User: always enable dark theme", source="flex") is False
    assert len(warm.all_facts()) == 1


def test_vector_core_dedupe(tmp_path: Path):
    vs = VectorStore(tmp_path)
    a = vs.add("User: never wipe wishes on clear", meta={"source": "flex_wish"})
    b = vs.add("Flex-wish: User: never wipe wishes on clear", meta={"source": "flex_wish"})
    assert a
    assert b == a  # same id — skipped re-add
    assert vs.count() == 1


def test_vector_upgrades_to_flex_source(tmp_path: Path):
    vs = VectorStore(tmp_path)
    a = vs.add("always use ruff before push", meta={"source": "requirement"})
    b = vs.add("User: always use ruff before push", meta={"source": "flex_wish"})
    assert a and b == a
    assert vs.count() == 1
    doc = vs.get(a)
    assert doc is not None
    assert doc["meta"].get("source") == "flex_wish"
    assert doc["text"].lower().startswith("user:")
