"""Clarify trigger: real ambiguity only."""

from gnom_hub.agents.roles_helpers import _needs_clarify


def test_hedge_triggers():
    assert _needs_clarify("maybe dark mode?")
    assert _needs_clarify("Vielleicht ein Dashboard")
    assert _needs_clarify("eventuell offline first")
    assert _needs_clarify("Should we use dark mode maybe?")


def test_or_choice_triggers():
    assert _needs_clarify("React oder Vue für die UI")
    assert _needs_clarify("light or full implementation")
    assert _needs_clarify("MVP oder gründlich")


def test_decision_seeking_triggers():
    assert _needs_clarify("Sollen wir Dark Mode nehmen?")
    assert _needs_clarify("what do you think about the layout")


def test_clear_build_with_question_mark_skips():
    assert not _needs_clarify("Baue mir eine Todo-App mit Dark Mode?")
    assert not _needs_clarify("Build a landing page with hero and footer?")
    assert not _needs_clarify("Create a single-file HTML dashboard?")


def test_clear_build_without_hedge_skips():
    assert not _needs_clarify("Build a landing page for Bean Shop full HTML")
    assert not _needs_clarify("Baue eine Checklisten-App")


def test_bare_vague_question_triggers():
    assert _needs_clarify("Dark mode?")
    assert _needs_clarify("Was ist besser?")


def test_mehr_oder_weniger_not_choice():
    assert not _needs_clarify("mehr oder weniger fertig mit dem HTML")
