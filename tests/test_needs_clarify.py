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


def test_brainstorm_tradeoff_triggers():
    assert _needs_clarify(
        "Checklist app",
        "Ideen: Variante A schnell, Variante B gründlich. Offene Frage: MVP oder robust?",
    )


def test_brainstorm_cta_alone_does_not_trigger():
    # Standard stub ending must not force clarify on a clear task
    notes = "Ideen zu: Todo\n• MVP\n→ Soll ich das jetzt umsetzen / den Plan erstellen?"
    assert not _needs_clarify("Build a todo app with dark mode HTML", notes)


def test_brainstorm_hedge_with_vague_user():
    assert _needs_clarify(
        "eine App",
        "Vielleicht offline-first. Noch unklar ob PWA oder native.",
    )


def test_user_clear_build_beats_generic_brainstorm_question():
    notes = "Ideen…\n→ Soll ich das jetzt umsetzen?"
    assert not _needs_clarify(
        "Baue eine Landingpage mit Hero und Footer, full HTML",
        notes,
    )


def test_brainstorm_react_or_vue_triggers():
    assert _needs_clarify(
        "UI neu",
        "Brainstorm: React oder Vue für die Komponenten?",
    )
